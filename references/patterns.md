# Workflow Patterns

This catalog distills reusable workflows from production Abaqus automation
scripts. When you need to do one of these things, mimic the pattern —
don't reinvent it.

## 1. Model creation / copy / rename

**Reference:** `build_models.py`, `workflow/stage1_build/build_models.py`

```python
# NEW_NAME / SRC_NAME from the User inputs block
# Copy starting model → derived model
if NEW_NAME in mdb.models:
    del mdb.models[NEW_NAME]
model = mdb.Model(name=NEW_NAME, objectToCopy=mdb.models[SRC_NAME])
model.rootAssembly.regenerate()      # important after copy
```

For derivative models (e.g., X model from Cross): copy → `assembly.rotate(...)` → `delete_fin_features(model)` → re-create features. Reference points may renumber after `regenerate()`, so always look them up by feature name or coordinate, never by ID.

## 2. Set & surface promotion (part → assembly)

**Reference:** `build_models.py::promote_sets`, `split_finbase`

Element sets keep their original name; node sets get a `_Node` suffix so
both can coexist on the assembly. This is the project convention — keep
it consistent so `assembly.sets['Engine_Node']` always means *the node
set derived from the part-level Engine elset*.

For partitioning a finbase set into 4 quadrants by `atan2(z, y)`, see
`split_finbase()`. Pattern: iterate elements, average node coords,
bucket by angle, build new sets via `instance.elements.sequenceFromLabels(...)`.

## 3. Reference points: create / find / dedupe

**Reference:** `scripts/skill_template.py::find_existing_rp`, `cleanup_dup_rps.py`,
`inspect_rps.py`

Always check before creating:

```python
# helper: copy from scripts/skill_template.py
existing_key = find_existing_rp(assembly, x, y, z, tolerance=10.0)
if existing_key is not None:
    rp_key = existing_key
else:
    feat = assembly.ReferencePoint(point=(x, y, z))
    rp_key = feat.id
```

Use `inspect_rps.py` (or the bundled `scripts/inspect_model.py`) to audit RPs before/after work.

## 4. Couplings — DISTRIBUTING vs KINEMATIC

**Reference:** `build_models.py::create_fin_loads`, `add_engine_mass`,
`add_pfs_truss_mass.py::apply_pfs_mass`,
`apply_section_loads.py::create_fwd_rp_and_coupling`

Project default: `DISTRIBUTING + WHOLE_SURFACE + UNIFORM` for fin RP →
shell finbase. For RP → beam node ring (engine, PFS truss, fwd ring),
add `rotationalCouplingType=ROTATIONAL_STRUCTURAL` to preserve moment
transfer (beams don't have shell-style rotation DOFs by default).

| Target geometry | Region kind | rotationalCouplingType |
|-----------------|-------------|------------------------|
| Shell elements (finbase) | `assembly.surfaces[...]` (side1Elements) | omit (default) |
| Beam element node ring (engine, fwd, truss) | `regionToolset.Region(nodes=...)` | `ROTATIONAL_STRUCTURAL` |

Use `KINEMATIC` only when you actually want to add rigid stiffness — rare in this project.

## 5. Concentrated forces & moments

**Reference:** `build_models.py::create_fin_loads`,
`apply_section_loads.py::setup_model`, `set_thrust.py`,
`fix_cross_finloads.py`

Aero force decomposition follows the project formula:

```python
# Q, AREF from the User inputs block
fn = cn * Q * AREF                          # normal (lift) component
fa = ca_per_fin * Q * AREF                  # axial (drag) component
fx = fa                                     # +X (drag opposes -X flight)
fy, fz = fn * ny, fn * nz                   # normal direction unit vector (ny, nz)
```

`follower=ON` is convention for fin loads (the load rotates with the
deformed fin). It requires a nonlinear step (NLGEOM=ON).

To update an existing load magnitude without recreating it:

```python
model.loads['EngineThrust'].setValues(cf3=NEW_CF3)
# or, in a different step:
model.loads['EngineThrust'].setValuesInStep(stepName='Step-2', cf3=UNCHANGED)
```

## 6. Pressure loads (mapped CFD field)

**Reference:** `apply_aero_pressure.py`

Workflow: build a single OML surface by concatenating all skin element
sets (`Skin`, `Skin_UpFlange`, `Skin_Payload`, `Skin_FinBase`) → create
`MappedField(pointDataFormat=XYZ, fieldDataType=SCALAR, xyzPointData=<txt>)`
from CFD CSV → apply `Pressure(distributionType=FIELD, magnitude=±1.0)`.
The `magnitude` scalar acts as a sign-flippable scale.

## 7. Gravity / inertia relief

**Reference:** `apply_section_loads.py::setup_model`, `toggle_gravity.py`

Body-force gravity: `model.Gravity(comp1=-9806.65, ...)` for 1 g in -X.
For the project's MaxQ trim, `comp1` is set to whatever value balances
remaining axial force after thrust + drag are accounted for.

Inertia relief enables all 6 DOFs (`u1=u2=u3=ur1=ur2=ur3=1`) — the
solver returns IRA (acceleration), IRF (reaction force), IRM (reaction
moment) as history variables. These are the keys for diagnostic and
calibration loops.

## 8. Point masses & non-structural masses

**Reference:** `build_models.py::add_fin_mass`, `add_engine_mass`,
`add_payload_mass`, `add_engine_nsm`,
`add_pfs_truss_mass.py`, `mass_breakdown.py`

| Use case | API call | Where the mass lives |
|----------|----------|----------------------|
| Discrete mass at a few RPs (engine, fins, PFS) | `assembly.engineeringFeatures.PointMassInertia` | One MASS element per RP, value as given |
| Distributed mass over an element set (payload, fuel) | `part.engineeringFeatures.NonstructuralMass(units=TOTAL_MASS, distribution=MASS_PROPORTIONAL)` | NSM stored on the part, distributed at solve time |

Important: `PointMassInertia` writes the given mass at *each* RP in the
region. If you have a *total* mass for N fins, pass `total / N`.

## 9. Equation constraints (cylindrical pairing)

**Reference:** `create_eq_constraints.py`, `inspect_eq_sets.py`

Project pattern: cylindrical CSYS (csys-2, ID 120 in this project) →
sort engine-side and structure-side ring nodes by azimuth → match
indices → create two equations per pair (radial DOF1, tangential DOF2),
leaving axial DOF3 free for relative motion. Names follow
`Eq_R_<tag>_N` / `Eq_T_<tag>_N`. Use `inspect_eq_sets.py` to validate
that the angle delta between paired nodes is < 5°.

`from caeModules import *` is required; without it `model.Equation` is
unbound in noGUI scripts.

## 10. Job submission & reporting

**Reference:** `run_jobs_and_report.py`

```python
job = mdb.Job(
    name=job_name, model=model_name, type=ANALYSIS,
    numCpus=4, numDomains=4, memory=90, memoryUnits=PERCENTAGE,
)
job.submit(consistencyChecking=OFF)
job.waitForCompletion()
# Then open the .odb and pull IRA/IRF/IRM via odbAccess.
```

Skip-if-done is convention: check `os.path.exists('%s.odb' % job_name)`
before resubmitting. Save the per-model results dict to
`aero_job_report.json` for downstream tooling.

## 11. Inspection / diagnostics

**Reference:** under `workflow/stage3_verify/`:
`inspect_rps.py`, `list_loads.py`, `list_sets.py`,
`mass_breakdown.py`, `diag_moments.py`, `read_ir_acceleration.py`,
`extract_ir.py`, `inspect_eq_sets.py`. Plus `scripts/inspect/inspect_cae.py`
and `scripts/inspect/inspect_sa.py` for additional model-tree dumps.

Use the bundled `scripts/inspect_model.py` (in this skill) as the single
entry point for "what's in this CAE?" — it covers steps, parts, sets,
surfaces, RPs (with duplicate detection), constraints, loads, masses,
and totals.

Use `extract_ir.py` for postprocessing-only ODB reads (runs in `abaqus
python`, no CAE GUI).

## 12. Model surgery (rename, fix orientations, delete orphans)

**Reference:** under `scripts/fixes/`:
`check_beam_orient.py`, `verify_orient.py`,
`fix_stringer_orient.py`, `fix_all_beam_orient.py`,
`find_orphan_nodes.py`, `delete_orphan_nodes.py`,
`fix_sa.py`, `fix_sa_regions.py`. Set/section renaming is handled
by `workflow/stage0_cleanup/rename_sets_auto.py` and
`rename_sections_auto.py`.

These scripts modify a CAE in-place and then call `mdb.save()`. Always:

1. Run the matching `inspect_*` script first to see what would change.
2. Run the fix script.
3. Re-run inspect to confirm.

For beam orientations, the convention is `n1 = (0,1,0)` (Y up); fix
scripts iterate beam sections and update the orientation if it deviates.

## 13. Beam orientation (n2 inward) on a part with mixed-winding mesh

**Reference:** `workflow/stage1_build/set_beam_orientation.py`,
`workflow/stage3_verify/inspect_one_ring.py` (cross_new work, 2026-04).

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

## 14. Find beam elements within a shell-element node footprint

**Reference:** `workflow/stage1_build/find_finbase_beams.py` (cross_new
fin-base beam set construction, 2026-04).

Pattern for "give me the beam elements that live inside region X
defined by a shell element set":

1. Walk the shell elset, collect all unique node labels + coordinates.
2. Optionally bin nodes by some spatial criterion (e.g., per-fin by
   `atan2(z, y)` quadrant).
3. For each candidate beam elset, keep beam elements whose **every**
   node label is in the bin.

```python
node_coords = {}
for sh in part.sets[SKIN_FINBASE_SET].elements:
    for n in sh.getNodes():
        node_coords.setdefault(n.label, n.coordinates)

# Bin into 4 fins by atan2 around +X
fb_nodes_by_fin = {1: set(), 2: set(), 3: set(), 4: set()}
for nlbl, c in node_coords.items():
    fb_nodes_by_fin[fin_id_for_angle(math.atan2(c[2], c[1]))].add(nlbl)

# Beam elements with ALL nodes in this fin's node bin
matching = []
for sn in BEAM_SETS:
    for e in part.sets[sn].elements:
        if all(n.label in fb_nodes_by_fin[fid] for n in e.getNodes()):
            matching.append(e.label)

part.Set(name='FINBASE_%d_BEAM' % fid,
         elements=part.elements.sequenceFromLabels(matching))
```

`getNodes()` returns the connectivity nodes for the element; comparing
labels is much faster than coordinate-matching, and avoids tolerance
hassles.

## 15. Promote part sets to assembly when the instance is broken

**Reference:** `workflow/stage1_build/promote_finbase_remove_hat.py`.

Some models have a stale internal part-name reference in the instance
(e.g., from a prior `ModelFromInputFile` + `changeKey`), which makes
`inst.part`, `inst.sets`, `inst.elements` raise. You can still create
assembly sets directly from element labels:

```python
labels = tuple(e.label for e in part.sets[sn].elements)
if sn in asm.sets:
    del asm.sets[sn]
asm.SetFromElementLabels(
    name=sn,
    elementLabels=((INSTANCE_NAME, labels),),
)
```

`SetFromElementLabels` only needs the instance *name string*, not the
instance object, so it sidesteps the broken `inst.part` traversal.

## 16. Per-region load consolidation after .inp re-import

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

## 17. Pressure direction verification (SPOS vs SNEG)

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

## 18. Per-load IR isolation via `load.suppress()`

**Reference:** `workflow/stage3_verify/run_no_thrust_irm2.py`,
`run_per_load_suppress.py`

When MaxN already has `*Inertia Relief` and the IR history-output request
configured (which it does in cross_new — verified via `Job-11.inp` lines
16600-16624), the cleanest way to isolate any single load is:

```python
# MODEL_NAME from the User inputs block
m = mdb.models[MODEL_NAME]
m.loads[LOAD_NAME].suppress()       # turns off this load only
# (or in a loop: suppress every other load, leave one active)
job = mdb.Job(name=JOB, model=MODEL_NAME, type=ANALYSIS, ...)
job.submit(consistencyChecking=OFF); job.waitForCompletion()
# read ODB IRF/IRM
m.loads[LOAD_NAME].resume()         # restore in-memory only
# DO NOT mdb.save() so disk state stays unchanged
```

**Why suppress beats clone:** cloning a `Pressure` load with `DISCRETE_FIELD`
distribution onto a different surface (when the original is bound to an
internal `_M<N>` surface — see api gotcha #30) reproduces the IR contribution
incorrectly (see api gotcha #31). Suppress hits the original surface binding
exactly as the solver would, so the IR result is authoritative.

**N-job per-load decomposition** (vs. cloning into perturbation steps in one
job): suppress-based runs N separate jobs of the actual MaxN step. Each job
costs solver time but uses only one CAE license (sequentially), so this is
the right trade for trim-critical analysis where DiscField pressures are
involved.

## 19. Linear superposition for trim tuning

**Reference:** `workflow/stage3_verify/run_no_thrust_irm2.py`

For inertia-relief problems, the system is linear in the applied loads.
Two data points are enough to solve for any "moment arm" parameter without
needing CG geometry:

```
IRM2_full   = IRM2_no_thrust + arm * cf3
arm         = (IRM2_full - IRM2_no_thrust) / cf3            # solve from any (cf3, IRM2) pair
cf3_target  = -IRM2_no_thrust / arm                          # solve for IRM2 = 0
```

**Process:**
1. Run with `SideThrust.suppress()` → record `IRM2_no_thrust`, `IRF3_no_thrust`.
2. Run with full loads (current cf3) → record `IRM2_full`.
3. Compute `arm = (IRM2_full - IRM2_no_thrust) / cf3_current`.
4. Required `cf3 = -IRM2_no_thrust / arm`.

**Sanity check:** the arm should be roughly constant across cf3 values.
If two different (cf3, IRM2_full) measurements give different arms, the
system is non-linear OR the loads were edited between runs (see api
gotcha #33).

**Why not just iterate?** One iteration is fine when both signs of the
non-thrust IRM2 may show up across runs (e.g., user toggling AeroPressure
sign in CAE GUI). Two-point linear solve gives the answer in one cycle
regardless of starting point.

## 20. Cross-model node copy by coordinate (not by label)

**Reference:** `workflow/stage2_loads/setup_cross_eq_prereqs.py`

When you want to recreate a node set from one model in another (e.g., copy
`engine_eq_1` from `Source_Model` to `Target_Model`), node labels
do NOT match across models — even if they share the same starting `.cae`,
ModelFromInputFile can renumber nodes. Always copy by **coordinate**:

```python
def copy_set_by_coord(src_model, tgt_model, set_name, tol_mm, log_fn):
    src = src_model.rootAssembly.sets[set_name]
    src_coords = [(n.coordinates, n.label) for n in src.nodes]
    tgt_inst = tgt_model.rootAssembly.instances[INSTANCE_NAME]
    matched = []
    for (sx, sy, sz), src_lbl in src_coords:
        # nearest-neighbor scan
        best, best_d2 = None, None
        for tn in tgt_inst.nodes:
            tx, ty, tz = tn.coordinates
            d2 = (tx-sx)**2 + (ty-sy)**2 + (tz-sz)**2
            if best_d2 is None or d2 < best_d2:
                best, best_d2 = tn.label, d2
        if best_d2 ** 0.5 > tol_mm:
            return None              # fail loudly
        matched.append(best)
    seq = tgt_inst.nodes.sequenceFromLabels(tuple(matched))
    tgt_model.rootAssembly.Set(name=set_name, nodes=seq)
```

Tolerance: 1.0 mm catches the typical sub-mm node-position drift from
re-meshing while flagging genuine topology mismatches. Print every match
distance — sub-0.1 mm is normal; > 0.5 mm warrants investigation.

## 21. Cylindrical Datum csys for engine-ring equation constraints

**Reference:** `workflow/stage2_loads/setup_cross_eq_prereqs.py`

To couple radial+tangential DOFs (and free axial) between two co-axial
rings via `*Equation`, you need a CYLINDRICAL Datum csys with axis along
+X (the rocket longitudinal axis):

```python
assembly.DatumCsysByThreePoints(
    coordSysType=CYLINDRICAL,
    line2=(0.0, 0.0, 1.0),         # T direction = +Z at origin
    name='Datum csys-2',
    origin=(5000.0, 0.0, 0.0),     # any point on the rocket axis
    point1=(5000.0, 1.0, 0.0),     # R direction = +Y at origin
)
```

After R = +Y and T = +Z at origin, the cylinder Z-axis is R × T = +X. ✓

Then the equation references this csys via the 4-tuple form:
`(coeff, set_name, dof, csys_id)`:

```python
model.Equation(name='Eq_R_RF_1',
    terms=((1.0, 'engine_node_set', 1, 120),       # DOF1 = radial
           (-1.0, 'struct_node_set', 1, 120)))
```

CAE saves the csys with an integer `id` (here often 120 if the model is
fresh). Look it up by name + type at runtime rather than hard-coding:

```python
for k in assembly.datums.keys():
    d = assembly.datums[k]
    if type(d).__name__ == 'DatumCsys' and getattr(d, 'coordSysType', None) == CYLINDRICAL:
        csys_id = k; break
```

## 22. Section force extraction along the rocket axis

**Reference:** `workflow/stage3_verify/extract_aft_section_forces.py` (wrapper)

The framework's `extract_section_forces.py` does node-based NFORC cumulative
summation along X. Its component auto-detection only handles LV1-style tank
naming (`*_CYLINDER_SET`); for the aft section, write a thin wrapper that
imports its helpers and supplies cut stations manually:

```python
sys.path.insert(0, FRAMEWORK_DIR)
from extract_section_forces import (cumulate_section_forces,
                                    FORCE_TO_KN, MOMENT_TO_KNM, CSV_HEADER, _format_row)
from odbAccess import openOdb

# read NFORC1/2/3 -> per-(elem, node) sums -> per-node net force
# (see read_nforc_filtered in extract_aft_section_forces.py)
nodes = read_nforc_filtered(odb_path, set_prefix=None)

# manual cut stations: include endpoints so the plot shows full range
cuts = [xmin]
x = xmin + pitch
while x < xmax: cuts.append(x); x += pitch
cuts.append(xmax + 1e-3)              # post-end gives equilibrium total ≈ 0

results = cumulate_section_forces(nodes, cuts)
```

**Endpoint behavior:**
- `cut = xmin` → 0 nodes accumulated → IRF/IRM = (0, 0, 0).
- `cut = xmax + ε` → all nodes accumulated → IRF/IRM = global force balance
  (≈ 0 if IR-trimmed; non-zero residual is a sanity check on trim quality).

**Sign convention — mixed:** `cumulate_section_forces` returns the
cumulative *external* nodal force on the accumulated side of the cut.

For this project's downstream consumers (HyperX skin sizing etc.),
N_x stays as raw cumulative (textbook **tension-positive** for axial:
compression → negative N_x), while V/M are negated to read as the
internal load the section transmits:

```python
for c in cuts:
    for k in ('V_y', 'V_z', 'M_x', 'M_y', 'M_z'):
        c[k] = -c[k]
    # N_x left alone — tension-positive (compression negative)
```

Rocket aft section in MaxQ ascent reads N_x ≈ −30 kN (compressive drag).
If a different downstream tool wants compression-positive, negate N_x as
well — it's a per-project convention call.

**Filtered NFORC summation (e.g., SKIN-only):** when you want section forces
transmitted only through specific element sets (skin, ringframe, etc.),
restrict the elements before summing per-node:

```python
keep_elems = set()
prefix_u = 'SKIN'
for sn in inst.elementSets.keys():
    if sn.upper().startswith(prefix_u):
        for e in inst.elementSets[sn].elements:
            keep_elems.add(e.label)
# then in the per-(elem, node) sum loop: skip if elem_label not in keep_elems
```

**Plotting:** `plot_section_forces.py` from the same framework produces an
interactive HTML plot. Run via the conda env (NOT abaqus python) since it
needs only stdlib + a browser:

```bash
python plot_section_forces.py results.csv
```

## 23. Calibration loop

**Reference:** `calibration/calibrate.py`, `dat_parser.py`,
`correction_calculator.py`, `diagnostic_runner.py`, `load_applicator.py`

Three-phase loop:

1. **Density scale** — read `.dat` total mass, compare to target,
   compute scale factor, apply to material density.
2. **Force diagnostics** — split aero from section loads, run two
   diagnostic jobs, extract IR force/moment, derive trim parameters
   (gimbal angle, lateral accel, fuel moment arm).
3. **Apply corrections** — write back gimbal thrust, lateral accel
   gravity component, run final job.

Pure-math helpers (`correction_calculator.py`) work in plain Python 3;
the orchestrator (`calibrate.py`) runs in Abaqus Python 2 via
`abaqus cae noGUI=calibrate.py -- --cae <path> --loads <json> ...`.

## 24. ODB post-processing — reading history and field outputs

**Reference:** `workflow/stage3_verify/run_jobs_and_report.py`,
`workflow/stage3_verify/extract_ir.py`,
`D:\tmp\extract_ir_test1.py` (one-shot diagnostic)

### When to use `abaqus python` vs `abaqus cae noGUI`

| Mode | Command | License | Use case |
|------|---------|---------|----------|
| `abaqus python script.py` | `python` only | Read-only ODB, no CAE model needed |
| `abaqus cae noGUI=script.py` | `cae` license | Need both ODB read AND CAE model access |
| `abq20XX python script.py` | Version-specific | ODB written by a specific Abaqus version |

**Critical: ODB version must match the reader.** An ODB written by Abaqus 2024
cannot be opened by `abaqus` (2025) without upgrading first. Use the
version-specific launcher that matches the ODB's origin:

```python
# If test_1.odb was created by Abaqus 2024:
#   abq2024 cae noGUI=read_odb.py
#   abq2024 python read_odb.py
#
# If upgrading is needed (creates a NEW file, does not overwrite):
#   abaqus -upgrade -job test_1_upgraded -odb test_1
```

### Minimal ODB history-output extraction pattern

```python
# -*- coding: utf-8 -*-
from odbAccess import openOdb

odb_path = r'D:\path\to\your\job.odb'
out_path = r'D:\tmp\odb_results.txt'

odb = openOdb(odb_path, readOnly=True)

lines = []
for step_name, step in odb.steps.items():
    lines.append('Step: %s' % step_name)
    for ho_key, ho in step.historyRegions.items():
        lines.append('  Region: %s' % ho_key)
        for var in sorted(ho.historyOutputs.keys()):
            data = ho.historyOutputs[var].data
            if data:
                last_t, last_v = data[-1]
                lines.append('    %s = %.6e (t=%.4f)' % (var, last_v, last_t))

odb.close()

with open(out_path, 'w') as f:
    f.write('\n'.join(lines) + '\n')
```

**Always write to a file** — `print()` stdout from `abaqus cae noGUI` is
buffered and frequently returns empty in PowerShell (see conventions
"Reporting from inside Abaqus scripts").

### Filtering for IR variables (IRA/IRF/IRM)

Inertia Relief history outputs use these keys:

| Key | Meaning | Unit (mm-N-tonne) |
|-----|---------|-------------------|
| IRA1, IRA2, IRA3 | Translational acceleration (X, Y, Z) | mm/s² |
| IRAR1, IRAR2, IRAR3 | Rotational acceleration (RX, RY, RZ) | rad/s² |
| IRF1, IRF2, IRF3 | Residual force (X, Y, Z) | N |
| IRM1, IRM2, IRM3 | Residual moment (X, Y, Z) | N·mm |

Filter pattern:

```python
IR_TAGS = ('IRA', 'IRF', 'IRM')
for var in sorted(ho.historyOutputs.keys()):
    if any(var.upper().startswith(tag) for tag in IR_TAGS):
        last_val = ho.historyOutputs[var].data[-1][1]
        lines.append('    %s = %.6e' % (var, last_val))
```

Convert IRA to g for human-readable output: `ira_g = ira_mmss / 9806.65`.

### Whole-model energy & mass outputs

The `Assembly ASSEMBLY` history region also contains energy variables:

| Key | Meaning |
|-----|---------|
| ALLSE | Strain energy |
| ALLIE | Internal energy |
| ALLKE | Kinetic energy |
| ALLWK | External work |
| ETOTAL | Total energy |
| ALLAE | Artificial energy (hourglass) |

Check `ALLAE / ALLIE < 5%` as a mesh quality indicator (hourglass control).

### Field output extraction (stress, displacement)

```python
from odbAccess import openOdb

odb = openOdb(path='MyJob.odb', readOnly=True)
frame = odb.steps['MaxQ'].frames[-1]

# Max displacement
u_field = frame.fieldOutputs['U']
u3_max = max(abs(v.data[2]) for v in u_field.values)

# Max von Mises stress
s_field = frame.fieldOutputs['S']
mises_max = max(v.mises for v in s_field.values)

# Field output on a specific set
subset = s_field.getSubset(region=odb.rootAssembly.elementSets['SKIN'])
mises_skin = max(v.mises for v in subset.values)

odb.close()
```

### Common ODB gotchas

1. **Always `readOnly=True`** for post-processing — prevents accidental
   ODB corruption and avoids the write lock.
2. **ODB version mismatch** raises `OdbError: The database is from a
   previous release` — use the matching `abq20XX` launcher.
3. **`# -*- coding: mbcs -*-`** can cause `SyntaxError: 'mbcs' codec
   can't decode bytes` on some Abaqus versions — use `utf-8` instead.
4. **`print()` returns empty** in PowerShell capture of `abaqus cae noGUI`
   — always write results to a text/JSON file and read back.
5. **`odb.rootAssembly.elementSets`** keys may be UPPERCASE even if the
   CAE model had mixed case — match case-insensitively when looking up sets.
6. **Field output `.values` can be huge** — filter by set/region first
   with `getSubset()` to avoid memory issues on large models.

## 25. Wire features + edge sets by featureName

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

## 26. Cross-model material / profile / section transfer

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

## 27. Hold-ring equation constraints (nearest-node radial pairing)

**Reference:** `scripts/fixes/eq_hold_ring2_buckhead.py`,
`scripts/fixes/find_engine_rings.py`,
`scripts/fixes/find_closest_engine_ring.py` (2026-06)

Couple a structural ring to the nearest engine nodes in the radial DOF
only (cylindrical CSYS), leaving tangential/axial free:

1. Collect both node sets with coordinates (part-level set → resolve via
   `inst.nodes.sequenceFromLabels((label,))` to get instance coords).
2. Sort the ring nodes by azimuth `atan2(z, y)`.
3. For each ring node, nearest-neighbor scan the engine nodes; log the
   min/max pair distance as a sanity check.
4. Delete stale per-pair sets/constraints by name prefix, then create
   one single-node set per side and one `Equation` per pair:

```python
model.Equation(name='Eq_R_HR2_%d' % idx,
    terms=((1.0, set_a, 1, CYL_KEY), (-1.0, set_b, 1, CYL_KEY)))
```

`CYL_KEY` is the cylindrical Datum csys id — look it up at runtime (see
§21), don't hardcode across models.

## 28. Set-name length limit (80 chars, qualified name)

**Reference:** `scripts/inspect/check_long_names.py`,
`scripts/fixes/rename_long_sets.py` (2026-05)

The solver limit is **80 characters** — and it applies to the
*qualified* name the .inp actually writes (`INSTANCE.setname`,
`ASSEMBLY.setname`), not just the bare set name. Imported models
accumulate auto-generated names that blow past this silently until job
submission. Audit both forms:

```python
for name in a.sets.keys():
    if len('ASSEMBLY.%s' % name) > 80:
        flag(name)
for inst_name in a.instances.keys():
    for sname in a.instances[inst_name].sets.keys():
        if len('%s.%s' % (inst_name, sname)) > 80:
            flag(sname)
```

Fix by renaming to a short deterministic scheme before job submission.

## 29. Advanced parametric modeling techniques (from WingsCrackTracer3)

**Reference:** WingsCrackTracer3 CAE plugin (composite ply-drop modeler).
Study for technique, not for style — see anti-patterns at the end.
Cohesive-element workflow deliberately NOT catalogued.

### 29.1 Staged function pipeline

`load_data → Partition → offset_faces → Loft → Mesh` — one function per
stage, single responsibility, re-runnable in isolation. This is the
skeleton every semi-automated modeling script should copy.

### 29.2 Sketch-driven face partitioning

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

### 29.3 Layer stacking via instance array + boolean merge

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

### 29.4 Coordinate bookkeeping instead of index access

Store `pointOn` / `getCentroid()` coordinates at creation time; find
entities back later with `findAt(coords)`. Indices renumber after any
feature operation — coordinates survive:

```python
face_coord = [f[i:i + 1].pointsOn[0] for i in drop_order]  # record now
faces = f.findAt(*face_coord)                              # find back later
```

### 29.5 Per-cell material orientation + sweep path

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
  bookkeeping (§29.4) or label/name lookup.
- GUI coupling (`session.viewports[...]`) in modeling logic → keep
  display calls out of noGUI scripts.

## Cross-cutting conventions

- **Idempotency**: Every script that modifies the model checks for
  pre-existing features (`if 'Name' in container`) and either reuses or
  deletes-and-recreates. Never assume a clean slate.
- **Logging**: redirect stdout to `_<scriptname>.log` via shell.
  Inside the script, `print(...)` to that log; no `logging` module.
- **JSON reports**: results-bearing scripts write a sibling `*.json`
  with the headline numbers. Downstream tools consume the JSON, not the
  script's stdout.
- **User inputs block**: every tunable value lives in a clearly marked
  block at the top of the script, one value per line, with a comment
  explaining the source (Excel cell, drawing, requirement doc). Editing
  parameters must never require touching the logic below the block.
