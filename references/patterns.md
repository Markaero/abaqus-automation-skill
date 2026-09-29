# Workflow Patterns

Multi-step workflows that the abqlib function library does not cover.
Single operations — model copy, sets and surfaces, reference points,
couplings, equations, loads, masses, jobs, ODB reads, deletion order —
are in abqlib: see `references/api_catalog.md` and the routing table in
`AGENTS.md`. API details are in the official docs (`tools/api_lookup.py`).

**About the `Reference:` lines:** they name the script in the origin
project where the pattern was proven. They are provenance, not files
shipped with this kit. If the user's project has a script of that name,
reuse it; otherwise implement from the snippet here.

| § | Pattern | Use when |
|---|---------|----------|
| 1 | Beam orientation (n2 inward) on a mixed-winding mesh | Beam webs must point radially inward regardless of element direction |
| 2 | Beam elements inside a shell-element node footprint | Building a beam set from the region a shell set covers |
| 3 | Per-region load consolidation after `.inp` re-import | Imported model has one load per force component |
| 4 | Pressure direction verification (SPOS vs SNEG) | Before trusting the sign of any surface pressure |
| 5 | Wire features + edge sets by `featureName` | Rebuilding wire geometry idempotently |
| 6 | Cross-model material / profile / section transfer | Moving a few named definitions between models |
| 7 | Advanced parametric modeling techniques | Sketch partitions, layer stacking, per-cell orientation |

## 1. Beam orientation (n2 inward) on a part with mixed-winding mesh

**Reference:** `workflow/stage1_build/set_beam_orientation.py`,
`workflow/stage3_verify/inspect_one_ring.py` (2026-04).

Goal: make the beam web (n2) point radially inward (toward the body
axis) for ring frames and stringers, regardless of how the mesher
oriented each B31 element. Right-hand rule: `t1 × n1 = n2`. We pick
`n1` per element so that `n2 = -r̂`.

**Critical lesson — what does *not* work:**

- `keywordBlock.replace(...)` to flip n1 strings: cosmetic, doesn't
  propagate to the model state used at job submission.
- `ModelFromInputFile` to round-trip the mesh: it normalizes B31
  connectivity to *lower-label-first*, so any flip you put into the
  .inp gets undone. It also uppercases all set names and leaves the
  newly-created instance with a stale internal part-name reference if
  you `changeKey` the part afterward.

**What works — `assignBeamSectionOrientation` per-element with computed n1:**

```python
# Ring set (t1 in YZ plane). Partition by current winding so a single
# n1 sign gives n2 = -r̂ for every element in the partition.
for e in part.sets[set_name].elements:
    c0, c1 = e.getNodes()[0].coordinates, e.getNodes()[1].coordinates
    ymid = 0.5 * (c0[1] + c1[1]); zmid = 0.5 * (c0[2] + c1[2])
    ty = c1[1] - c0[1];           tz = c1[2] - c0[2]
    cross_x = ty * zmid - tz * ymid
    (pos_labels if cross_x > 0 else neg_labels).append(e.label)

if pos_labels:
    region = regionToolset.Region(elements=part.elements.sequenceFromLabels(pos_labels))
    part.assignBeamSectionOrientation(region=region, method=N1_COSINES, n1=(1.0, 0.0, 0.0))
if neg_labels:
    region = regionToolset.Region(elements=part.elements.sequenceFromLabels(neg_labels))
    part.assignBeamSectionOrientation(region=region, method=N1_COSINES, n1=(-1.0, 0.0, 0.0))
```

For axial stringers (t1 along ±X), assign per element:

```python
sign_tx = 1.0 if (c1[0] - c0[0]) > 0 else -1.0
n1 = (0.0, -zmid * sign_tx, ymid * sign_tx)   # gives n2 = -r̂
```

For YZ-plane sets (spokes, V-braces, buttress, disk) where t1 is in YZ
and n1 = (1, 0, 0) is automatically perpendicular: a single global n1
assignment is enough, Abaqus orthogonalizes per element.

For axial-leaning sets (ground-hold rails, PFS truss struts) that span
X with diagonal segments: a single n1 = (0, 0, 1) is a generic
perpendicular. n2 won't be cleanly r̂-aligned, but stays consistent.

**Verification pattern:** read the .inp `*Beam General Section` blocks
per element after the script runs and compare to expected n1 (within
tolerance for normalized direction). See `inspect_one_ring.py`.

**Visual sanity check:** apply an asymmetric `ArbitraryProfile` (e.g.,
hat shape) to the target sets, open CAE, "Render beam profiles" → the
hat brim should face outward and the closed end inward. After
inspection, delete `Section-Hat` + the associated profile and re-run
section assignments. See `create_hat_section.py` and
`promote_finbase_remove_hat.py`.

## 2. Find beam elements within a shell-element node footprint

**Reference:** `workflow/stage1_build/find_finbase_beams.py` (2026-04).

Pattern for "give me the beam elements that live inside region X
defined by a shell element set":

1. Walk the shell elset, collect all unique node labels + coordinates.
2. Optionally bin nodes by some spatial criterion (e.g., per-fin by
   `atan2(z, y)` quadrant).
3. For each candidate beam elset, keep beam elements whose **every**
   node label is in the bin.

```python
node_coords = {}
for sh in part.sets[SHELL_SET].elements:
    for n in sh.getNodes():
        node_coords.setdefault(n.label, n.coordinates)

# Optional: bin nodes, e.g. into 4 quadrants by atan2 around +X
nodes_by_bin = {1: set(), 2: set(), 3: set(), 4: set()}
for nlbl, c in node_coords.items():
    nodes_by_bin[bin_for_angle(math.atan2(c[2], c[1]))].add(nlbl)

# Beam elements with ALL nodes in this bin
matching = []
for sn in BEAM_SETS:
    for e in part.sets[sn].elements:
        if all([n.label in nodes_by_bin[b] for n in e.getNodes()]):
            matching.append(e.label)

part.Set(name='REGION_%d_BEAM' % b,
         elements=part.elements.sequenceFromLabels(matching))
```

`getNodes()` returns the connectivity nodes for the element; comparing
labels is much faster than coordinate-matching, and avoids tolerance
hassles.

## 3. Per-region load consolidation after .inp re-import

**Reference:** `workflow/stage2_loads/consolidate_finloads.py`,
`workflow/stage2_loads/restore_fin_drag.py`.

After `ModelFromInputFile`, what was a single `ConcentratedForce(cf1=A, cf3=B)`
becomes two `CFORCE-N` loads on the same region (one per non-zero
component). To collapse back to one load per region:

1. Iterate `model.loads.keys()`. For each `ConcentratedForce`, read
   the actual values from the per-step load state (the `getattr(L,
   'cf1', ...)` accessor returns `None` after re-import — the values
   live on `model.steps[step].loadStates[load_name].cfN`).
2. Get the region's set name from `tuple(load.region)[0]` (a tuple of
   shape `(set_name, 'Assembly', n1, n2, n3)`).
3. Group by set name, sum cf1/cf2/cf3 per group. Same for `Moment` /
   cm1/cm2/cm3.
4. Delete the originals; create one consolidated `ConcentratedForce`
   (and one `Moment` if needed) per region with a meaningful name.

For combining RP sets across regions (e.g., one drag load on all 4
fin RPs), use `assembly.SetByBoolean(operation=UNION, sets=...)` —
this is entity-type-agnostic and works whether the underlying sets
hold RPs or imported nodes.

## 4. Pressure direction verification (SPOS vs SNEG)

**Reference:** `workflow/stage3_verify/_test_press_sign.inp`,
`workflow/stage3_verify/inspect_oml_normals.py`,
`workflow/stage3_verify/_probe_distforce_surface.py`.

Two independent things must be right for aero pressure:

1. **Shell connectivity normal direction**: for the OML, you want
   it OUTWARD. Verify with a script that computes
   `(N2-N1) × (N3-N1)` per shell and dots with the radial unit vector
   at the centroid (skip shells with small radius — fin-base ones
   tangential to YZ won't have a meaningful "outward").
2. **Surface side that the Pressure load is bound to**: SPOS or SNEG.
   `Surface(side1Elements=...)` creates an SPOS surface. But after
   `.inp` re-import, an internal surface `_M<N>` may end up
   `__M<N>_SNEG, SNEG` — the OPPOSITE side. **Check by dumping the
   inp via `Job.writeInput()` and grepping for the load's region
   surface name.**

Empirical convention (verified on Abaqus 2025 with single S4R
shell, normal = +X, surface created via `*Surface, type=ELEMENT, S1`
+ `*Dsload S1SURF, P, 1.0`): the shell deforms in **−normal**
direction. So:

- Side1 (SPOS) + positive Pressure → force from SPOS toward SNEG
  (i.e., opposite to +normal).
- For OML with +normal outward: positive gauge × `magnitude=+1.0`
  on SPOS surface → compresses body. Correct sign for external
  aero (high local pressure pushes inward).
- If the live load is bound to SNEG instead (post-import bug): same
  +1 multiplier pushes outward. Either re-bind to the SPOS surface
  or flip `magnitude` to `-1.0`.

Note: this is the *surface-based* convention (`*Dsload P`).
*Element-based* (`*Dload P`) on shells uses the OPPOSITE convention
("+ pressure in +normal direction"). Web docs frequently cite the
element-based one without clarifying — don't trust without
empirical check.

## 5. Wire features + edge sets by featureName

**Reference:** `build_wire_frames.py`

Part-level wire geometry is idempotent by deleting prior features first,
then rebuilding:

```python
old = [fn for fn in part.features.keys() if fn.startswith('Wire')]
if old:
    part.deleteFeatures(tuple(old))
for sn in ('Wire1_edges', 'Wire2_edges', 'Wire3_edges'):
    if sn in part.sets.keys():
        del part.sets[sn]
```

Collect the edges a wire feature created by matching `edge.featureName`
— robust against index renumbering:

```python
def edge_set_for_feature(feature_name, set_name):
    seq = None
    for e in part.edges:
        if e.featureName == feature_name:
            s = part.edges[e.index:e.index + 1]
            seq = s if seq is None else seq + s
    part.Set(name=set_name, edges=seq)
```

Snap plane stations to round values (e.g. 6702.99849 → 6703.0) to avoid
micron slivers against existing partitions.

## 6. Cross-model material / profile / section transfer

**Reference:** `build_beam_sections.py`

Manual re-creation with exist-checks beats copy utilities when only a
few named objects move. Pattern per object type:

```python
def make_material(name, elastic_table, density_table):
    if name in model.materials.keys():
        return
    mat = model.Material(name=name)
    mat.Elastic(table=elastic_table)
    mat.Density(table=density_table)

if 'HX_C_30x20' not in model.profiles.keys():
    model.ArbitraryProfile(name='HX_C_30x20',
        table=((19.0, 14.0, 0.0), (0.0, 14.0, 2.0),
               (0.0, -14.0, 2.0), (19.0, -14.0, 2.0)))
```

`ArbitraryProfile` table rows are `(x, y, t)`: first row is the start
point (its t is ignored, write 0.0), each later row draws a segment of
thickness t from the previous point.

Assignment + orientation in one loop, idempotent via the region names
recorded on existing `sectionAssignments` / `beamSectionOrientations`:

```python
assigned = set(sa.region[0] for sa in part.sectionAssignments)
for set_name, sec_name, n1 in assign_map:
    region = part.sets[set_name]
    if set_name not in assigned:
        part.SectionAssignment(region=region, sectionName=sec_name)
    part.assignBeamSectionOrientation(region=region,
                                      method=N1_COSINES, n1=n1)
```

## 7. Advanced parametric modeling techniques (from WingsCrackTracer3)

**Reference:** WingsCrackTracer3 CAE plugin (composite ply-drop modeler).
Study for technique, not for style — see anti-patterns at the end.
Cohesive-element workflow deliberately NOT catalogued.

### 7.1 Staged function pipeline

`load_data → Partition → offset_faces → Loft → Mesh` — one function per
stage, single responsibility, re-runnable in isolation. This is the
skeleton every semi-automated modeling script should copy.

### 7.2 Sketch-driven face partitioning

Parametric sketch (W, R, D1, D2 as function args) drawn on a transform
anchored to existing geometry, then partitioned:

```python
t = p.MakeSketchTransform(sketchPlane=f[0], sketchUpEdge=e[idx],
                          sketchPlaneSide=SIDE1, origin=origin)
s = model.ConstrainedSketch(name='__profile__', sheetSize=100.,
                            transform=t)
p.projectReferencesOntoSketch(sketch=s, filter=COPLANAR_EDGES)
s.rectangle(point1=(-0.5 * W - D1, D2), point2=(0.5 * W + D1, -D2))
s.ArcByCenterEnds(center=(-W / 2, 0), point1=p1, point2=p2,
                  direction=COUNTERCLOCKWISE)
p.PartitionFaceBySketch(sketchUpEdge=e[idx], faces=pickedFaces, sketch=s)
```

Draw geometry from parameters; never hardcode sketch coordinates that
depend on design values.

### 7.3 Layer stacking via instance array + boolean merge

Build a solid laminate by instancing a base face part N times, offsetting
each along the face normal, then merging:

```python
for x in range(n_layers):
    a.Instance(name='Local_Part_1-%d' % x, part=p, dependent=ON)
    a.translate(instanceList=('Local_Part_1-%d' % x,),
                vector=tuple(direction * (-z + t * x) * c
                             for c in normal))
a.InstanceFromBooleanMerge(name=part_name, instances=all_instances,
                           originalInstances=DELETE, domain=GEOMETRY)
```

Then `p.ShellLoft(loftsections=..., keepInternalBoundaries=ON)` connects
successive layer edges and `p.AddCells(faceList=f[:])` converts the
closed shell into solid cells.

### 7.4 Coordinate bookkeeping instead of index access

Store `pointOn` / `getCentroid()` coordinates at creation time; find
entities back later with `findAt(coords)`. Indices renumber after any
feature operation — coordinates survive:

```python
face_coord = [f[i:i + 1].pointsOn[0] for i in drop_order]  # record now
faces = f.findAt(*face_coord)                              # find back later
```

### 7.5 Per-cell material orientation + sweep path

Discrete orientation per cell, normal axis from a face region, primary
axis from a datum; sweep direction picked by dotting each cell edge with
the stack normal:

```python
p.MaterialOrientation(region=cell_region, orientationType=DISCRETE,
    axis=AXIS_3, normalAxisDefinition=SURFACE,
    normalAxisRegion=face_region, flipNormalDirection=flip,
    primaryAxisDefinition=DATUM, primaryAxisDatum=datum_axis,
    primaryAxisDirection=AXIS_1, angle=ply_angle, stackDirection=STACK_3)

for edge in cell.getEdges():
    if abs(round(dot(normal, unit_vector(edge)), 1)) == 1.0:
        p.setSweepPath(region=cell, edge=e[edge], sense=sense)
        break
```

### Anti-patterns observed (do NOT copy)

- `session.customData` / `mdb.customData` as global state between stages
  → pass values as function arguments; keep state in the User inputs
  block and explicit return values.
- `exec("%s = %d" % ...)` for dynamic variable names → use a dict.
- Index-positional access (`faces[0]`, `keys()[-1]`) → coordinate
  bookkeeping (§7.4) or label/name lookup.
- GUI coupling (`session.viewports[...]`) in modeling logic → keep
  display calls out of noGUI scripts.
