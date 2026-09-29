# Abaqus API: Look It Up, Plus What the Docs Don't Say

This file has two jobs: (1) how to look up the Abaqus scripting API, and
(2) the traps that the API documentation does **not** warn about. Anything
the docs already state (return types, index vs label, which repository an
object lives in, which members exist) is deliberately not repeated here —
look it up instead.

## Look Up Before You Call

Before using any Abaqus class, method or argument that abqlib does not
wrap (see `references/api_catalog.md`), read its documentation. Most
scripting mistakes are documented behavior nobody looked up.

1. **Offline, from the kit** — abqpy mirrors the official Scripting
   Reference as Python stubs with full docstrings, one release per Abaqus
   version (MIT, https://github.com/haiiliin/abqpy). One-time setup with
   plain Python 3.9+, matching the user's Abaqus version:

   ```bash
   pip install --no-deps --target .abqpy "abqpy==2024.*"   # run in the kit directory
   python3 tools/api_lookup.py ConcentratedForce            # class: members + docs
   python3 tools/api_lookup.py DatumCsysByThreePoints       # method: signature + args
   python3 tools/api_lookup.py --search Csys                # find names
   ```

   The output includes the "accessed by" path (e.g. which repository an
   object lives in) and `versionadded` notes for version-dependent
   arguments.
2. **Online** — https://haiiliin.github.io/abqpy, or the SIMULIA *Abaqus
   Scripting Reference* for the installed release (help.3ds.com or the
   local documentation install).
3. **The live object** in the user's CAE — a read-only probe that writes
   `textRepr.getIndentedRepr(obj, maxRecursionDepth=1)` to its report file
   (don't rely on stdout, trap #1). Use this when the docs and the model
   disagree.

What a lookup answers, for example:

| Question | The docs say |
|---|---|
| What does `assembly.ReferencePoint(...)` return? | A `Feature`; the RP is `assembly.referencePoints[feature.id]` |
| Is `inst.nodes[5]` node label 5? | No — arrays are indexed by position; use `sequenceFromLabels` |
| Where are a load's `cf1`/`magnitude` values? | Not on the load: on `model.steps[step].loadStates[name]` |
| Where is a `NonstructuralMass` stored? | `engineeringFeatures.inertias`, together with point masses |
| Can I pass `rotationalCouplingType` to `Coupling`? | Only on Abaqus 2024+ (`versionadded:: 2024`) |

## Traps the Docs Don't Tell You

Undocumented behavior, environment quirks and empirical findings. Read
the group that matches the situation.

### Every run: noGUI, PowerShell, CAE GUI

| # | Trap | What to do |
|---|------|------------|
| 1 | **stdout is lossy.** Under `abaqus cae noGUI` the launcher buffers output; PowerShell often captures nothing even on success | Write results to a report file (`abqlib.util.Report`, the template does this); treat the shell log as launcher noise only |
| 2 | **argv is unreliable.** Abaqus consumes or injects arguments | Put inputs in the User inputs block; if you must pass args, read only what follows `--` |
| 3 | **`__file__` is undefined** — noGUI runs scripts via `execfile` | Use absolute paths from the User inputs block (`ABQLIB_PATH`) or `os.getcwd()` |
| 4 | **`# -*- coding: mbcs -*-` can raise `SyntaxError`** on some Windows setups | Use `# -*- coding: utf-8 -*-` |
| 5 | **`from abaqus import *` replaces `sum`** with a version that rejects generators (`TypeError: ... found 'generator'`) | `sum([x for x in it])` |
| 6 | **The CAE GUI locks the file.** `openMdb` fails with "File open failed" / "0 out of 2 licenses available" while the `.cae` is open in the GUI | Ask the user to close CAE first |
| 7 | **The GUI does not refresh** after a script changes the `.cae` on disk | Tell the user to close and reopen the file before judging the result |
| 8 | **GUI edits change the model between runs** when the user keeps the `.cae` open and edits it | Dump current load values at the start of tuning scripts; if results drift, ask |
| 9 | **`assembly.getMassProperties()` can hang** in noGUI on imported assemblies (no exception, the run just stops) | Avoid it in batch scripts; take mass/CG from the `.dat` of a run instead |
| 10 | **ODB version mismatch**: `OdbError: ... previous release` | Run with the launcher of the Abaqus version that wrote the ODB (e.g. `abq2024 python`), or `abaqus -upgrade -job new -odb old` |

### Models imported from `.inp` (`ModelFromInputFile`, keyword edits)

| # | Trap | What to do |
|---|------|------------|
| 11 | **Keyword edits don't change mesh data.** `keywordBlock.replace()` on element/node lines has no effect on the model; with the default `synchVersions(storeNodesAndElements=False)` those lines aren't even in the block | Change mesh data through the API, not the keyword block |
| 12 | **B31 connectivity is normalized on import** (lower label first); node-order flips made in the `.inp` are undone | Set beam direction via `assignBeamSectionOrientation` per element (patterns §1) |
| 13 | **`changeKey` after import leaves stale references**: `instance.part` / `instance.sets` raise `KeyError` naming the old model | Use `model.parts[...]` directly and `assembly.SetFromElementLabels` / `SetFromNodeLabels` with the instance name (`sets.promote_part_set` does) |
| 14 | **All set / surface names become UPPERCASE** | Match names case-insensitively after import |
| 15 | **A `Pressure` can come back bound to the opposite side**: an internal `_M<N>` surface defined `SNEG`, while your named surface is `SPOS` | `writeInput()` and grep the load's surface for `SPOS`/`SNEG`; rebind or flip the sign (patterns §4) |
| 16 | **One `ConcentratedForce(cf1=A, cf3=B)` becomes one load per component** | Group by region and sum per component to consolidate (patterns §3) |
| 17 | **RP sets become node sets**: `assembly.sets[name].referencePoints` is empty | Combine with `SetByBoolean(operation=UNION, ...)`, which works for either entity type |
| 18 | **Internal `_M<N>` surfaces are not in `assembly.surfaces`** (`KeyError`) | Fall back to the equivalent named surface — and re-check the side (trap #15) |

### Beam section orientation

| # | Trap | What to do |
|---|------|------------|
| 19 | **`assignBeamSectionOrientation` accumulates**: each call adds a sub-elset and a `*Beam General Section` block; the last write per element wins | Per-element overrides are fine; to reset in bulk, delete and reapply with the same partition |
| 20 | **Abaqus 2025 `writeInput`/`synchVersions` refuse beam elsets without an explicit n1** | Assign a default `n1` to every beam elset first |

### Empirical findings (verify on your version)

| # | Trap | What to do |
|---|------|------------|
| 21 | **Pressure direction is easy to get backwards**: side1 = SPOS, side2 = SNEG, and a positive surface pressure pushes *against* the normal of the side it is bound to. Written descriptions are ambiguous, and element-based `*Dload P` was observed to behave differently | Before trusting a sign, run a one-element test and check the deformation direction (patterns §4) |
| 22 | **Cloning a `DISCRETE_FIELD` pressure onto another surface changes the result** (5–15 % IRF/IRM deviation observed) | Isolate loads with `suppress()` on the original load (`loads.suppress_all_but`), never with clones |
| 23 | **Frame of `inst.nodes[i].coordinates` is unconfirmed** — earlier notes in this kit disagreed (part frame vs assembly frame), and the docs don't say | Before relying on it for a moved/rotated instance, probe: compare `part.nodes[i]` and `inst.nodes[i]` coordinates |

## Invocation Patterns

| Mode | Command | Use case | Reads `.cae`? | Reads `.odb`? |
|------|---------|----------|---------------|---------------|
| noGUI script | `abaqus cae noGUI=script.py` | Build models, modify, submit | yes | yes |
| With args | `abaqus cae noGUI=script.py -- arg1 arg2` | Parameterized scripts (read args after `--`, trap #2) | yes | yes |
| Python only | `abaqus python script.py` | Postprocess `.odb` (no GUI overhead) | no | yes |
| Plain Python | `python script.py` (your own Python env) | Pure helpers (parsing JSON, math), `tools/*.py` | no | no |

## Building a Model from Scratch (Standalone Script)

These snippets cover the full one-shot path: empty `mdb` → part → material →
mesh → assembly → step → BC → load → ODB read. Pulled verbatim from a
validated cantilever beam test (1000×50×20 mm steel, tip −Z 100 N,
encastre on x=0). This is *not* the project pattern (which uses
`openMdb(CAE_PATH)` — `CAE_PATH` from the User inputs block — against
a pre-built CAE) — use only for one-shot standalone runs.

### Standalone-script preamble

You start from the auto-created `mdb` Abaqus provides at launch — no
`openMdb`, no `mdb.save()`. Change cwd before submitting so job
artifacts (`.odb`, `.sta`, `.msg`, `.dat`) land where you want.

```python
import os
os.chdir('D:/tmp/abq_skill_test')   # job artifacts land here
model = mdb.Model(name='Cantilever', modelType=STANDARD_EXPLICIT)
```

### Sketch + solid extrude

Rectangle in the part's X-Y plane, extrude in part-Z. Part-local axes
will equal global axes when the instance is created without rotation.

```python
sketch = model.ConstrainedSketch(name='__profile__', sheetSize=2000.0)
sketch.rectangle(point1=(0.0, 0.0), point2=(LX, LY))
part = model.Part(name='Beam', dimensionality=THREE_D, type=DEFORMABLE_BODY)
part.BaseSolidExtrude(sketch=sketch, depth=LZ)
del model.sketches['__profile__']
```

### Material + section + assignment

Note the nested-tuple shape — easy gotcha. Both `Elastic` and `Density`
take a tuple-of-tuples even when there's only one row: `((E, nu),)` and
`((rho,),)`. A single tuple `(E, nu)` raises.

```python
mat = model.Material(name='Steel')
mat.Elastic(table=((210000.0, 0.3),))     # (( E, nu ),)
mat.Density(table=((7.85e-9,),))          # tonne/mm^3 — single-value also nested!
model.HomogeneousSolidSection(name='SolidSec', material='Steel', thickness=None)
part.SectionAssignment(region=(part.cells,), sectionName='SolidSec')
```

### Mesh: element type, seed, generate

`import mesh` works inside `abaqus cae noGUI`; the `ElemType` class is
exposed there.

```python
from mesh import ElemType
part.setElementType(
    regions=(part.cells,),
    elemTypes=(ElemType(elemCode=C3D8R, elemLibrary=STANDARD),),
)
part.seedPart(size=10.0, deviationFactor=0.1, minSizeFactor=0.1)
part.generateMesh()
```

### Assembly + dependent instance

```python
assembly = model.rootAssembly
assembly.DatumCsysByDefault(CARTESIAN)
assembly.Instance(name='Beam-1', part=part, dependent=ON)
```

### Step + field output request

```python
model.StaticStep(name='Step-1', previous='Initial', nlgeom=OFF)
model.fieldOutputRequests['F-Output-1'].setValues(variables=('S', 'U', 'RF'))
```

### BC on a face picked by bounding box (encastre pattern)

```python
inst = assembly.instances['Beam-1']
tol = 1e-3
fixed_faces = inst.faces.getByBoundingBox(
    xMin=-tol, xMax=tol, yMin=-tol, yMax=LY+tol, zMin=-tol, zMax=LZ+tol)
assembly.Set(name='FixedEnd', faces=fixed_faces)
model.EncastreBC(name='Encastre', createStepName='Initial',
                 region=assembly.sets['FixedEnd'])
```

### Concentrated force on a node picked by proximity (tip-load)

```python
target = (LX, LY/2, LZ/2)
nodes = inst.nodes
best, best_d2 = None, 1e30
for n in nodes:
    d2 = sum([(n.coordinates[i] - target[i])**2 for i in range(3)])  # list, not generator (#16)
    if d2 < best_d2:
        best, best_d2 = n, d2
tip_set = assembly.Set(name='Tip', nodes=inst.nodes.sequenceFromLabels((best.label,)))
model.ConcentratedForce(name='Tip_Load', createStepName='Step-1',
                        region=tip_set, cf3=-100.0, distributionType=UNIFORM)
```

### Read field output last-frame max

Mirrors the history-output snippet above but pulls a field-output max.
`data[i]` is the i-th component (0=U1, 1=U2, 2=U3 for displacements);
`.mises` is a precomputed scalar invariant on stress tensors.

```python
from odbAccess import openOdb
odb = openOdb(path='Cant_Test.odb')
frame = odb.steps['Step-1'].frames[-1]
u3_max = max(abs(v.data[2]) for v in frame.fieldOutputs['U'].values)
mises_max = max(v.mises for v in frame.fieldOutputs['S'].values)
print('Max |U3| = %.4f mm' % u3_max)
print('Max Mises = %.4f MPa' % mises_max)
odb.close()
```
