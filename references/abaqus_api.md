# Abaqus Python Scripting API Reference

Condensed reference for the Abaqus/CAE scripting API. Source: Abaqus
Scripting Reference Guide v6.6–2017, abqpy docs, project field experience.

## API Gotchas

The first 10 are the everyday ones (mirrored in `AGENTS.md`); 11+ are
import/round-trip, noGUI-runtime, and ODB traps.

| # | Gotcha | Why it bites | Fix |
|---|--------|--------------|-----|
| 1 | **Index != Label** | `inst.nodes[5]` is the 6th node in the array, not node label 5 | `inst.nodes.sequenceFromLabels([5])` |
| 2 | **connectivity = indices** | `elem.connectivity` returns *internal indices*, not node labels | `elem.getNodes()` returns `MeshNode` objects with `.label` |
| 3 | **Coordinates are in part frame** | A rotated/translated instance still reports node coords in the part's local frame | Manually transform if you need global coords on a rotated instance |
| 4 | **`ReferencePoint()` returns Feature** | Not a `ReferencePoint` — you can't pass it where a region expects an RP | Use `feat.id`, then `assembly.referencePoints[feat.id]` |
| 5 | **Trailing comma for 1-tuple** | `(rp)` is just `rp`; not a tuple | `referencePoints=(rp_obj,)` — comma matters |
| 6 | **side1 vs side2** | Wrong side flips pressure/contact normal sign — silently | side1 = positive normal (SPOS); side2 = negative (SNEG). For `Pressure` loads, **positive `magnitude` pushes INTO the selected face** (opposite to its outward normal). |
| 7 | **Region is temporary; Set is persistent** | A `regionToolset.Region` reference goes stale after `regenerate()` | Use `assembly.Set(...)` if you need the region to survive |
| 8 | **Delete order matters** | Deleting an RP before its constraint/load raises | Loads → constraints → sets/surfaces → RP features |
| 9 | **DISTRIBUTING ≠ KINEMATIC** | KINEMATIC adds rigid stiffness (RBE2); DISTRIBUTING does not (RBE3) | DISTRIBUTING for load spreading; KINEMATIC for rigid joints |
| 10 | **`from caeModules import *` required in noGUI** | `model.Equation`, `model.Coupling`, `model.Tie` are unbound otherwise | Always include in noGUI scripts that build constraints |
| 11 | **`keywordBlock.replace()` is cosmetic** | Edits the input deck text representation but does NOT propagate to the model's mesh data; `writeInput()` regenerates from model state, ignoring keyword block edits | Useless for changing element connectivity. Use the proper API or `ModelFromInputFile` round-trip (with caveats — see #13) |
| 12 | **`synchVersions(storeNodesAndElements=False)` excludes elements** | Default flag drops `*Element` blocks from the keyword text, so any search/replace on element data lines finds nothing | Pass `storeNodesAndElements=True` explicitly when you need to read or edit element data lines |
| 13 | **`ModelFromInputFile` normalizes B31 connectivity** | After import, beam element node order is forced to a canonical form (often lower-label-first); flips you made in the .inp text get silently undone | Cannot reliably reverse element direction via .inp round-trip. Accept the mesh winding and adapt orientation per element instead |
| 14 | **`ModelFromInputFile` + `changeKey` leaves stale internal refs** | The renamed model's `instance.part` / `instance.sets` raises `KeyError` pointing to the OLD model name; the model is otherwise functional | Access part data directly via `model.parts['PART-1']` (bypasses the broken accessor); use `assembly.SetFromElementLabels` for assembly sets |
| 15 | **`ModelFromInputFile` uppercases all set names** | Imported model has all elsets/nsets in UPPERCASE regardless of mixed-case original | Update set name constants to uppercase, or run a renaming pass after import |
| 16 | **`from abaqus import *` shadows builtin `sum`** | Abaqus's overridden `sum` rejects generator expressions: `TypeError: arg1; found 'generator', expecting a recognized type` | Use list comprehensions: `sum([x for x in iter])` not `sum(x for x in iter)` |
| 17 | **stdout in noGUI is buffered/lossy** | Final `print()` output sometimes never reaches the captured log even on EXIT=0 | For critical output, append to a `lines = []` list and write to a sibling `_<scriptname>.txt` report file at script end |
| 18 | **Argv parsing in noGUI is unreliable** | Abaqus consumes some args before `--`, may inject its own flags (`-cae`, etc.), or pass the script path back into argv | Hardcode constants when possible; if you must use argv, filter out `-`-prefixed and validate |
| 19 | **`assignBeamSectionOrientation` accumulates** | Each call creates a sub-elset (`_I<N>`) and a `*Beam General Section` block; multiple calls for overlapping elements all stick — last write per element wins | Per-element overrides are fine; for bulk reset, delete and reapply with the same partition logic |
| 20 | **`synchVersions` requires explicit beam orientations** | Abaqus 2025 refuses to regenerate the input deck if any beam-section-assigned elset lacks an explicit n1 | Pre-assign a default `n1=(0,0,1)` (or any unit vector) to every beam elset before calling `synchVersions` or `writeInput` |
| 21 | **CAE GUI file lock blocks noGUI scripts** | When the .cae is open in CAE GUI, `openMdb` errors with "File open failed" and you see "0 out of 2 licenses available" | Close CAE entirely before running scripts; the GUI takes one of the licenses too |
| 22 | **CAE viewer doesn't auto-refresh on external edits** | User opens CAE, an external script modifies the .cae on disk, the GUI keeps showing the snapshot from when it was opened | After running a script, instruct the user to `File → Close` and reopen the .cae — failure to do this causes false "didn't work" diagnoses |
| 23 | **`*Dsload P` direction (verified empirically)** | For a surface created with `side1Elements=`, positive `Pressure(magnitude)` pushes the shell **OPPOSITE** to its +normal direction (from SPOS face toward SNEG). The same convention but the *opposite* of element-based `*Dload P` on shells. Web docs are ambiguous; only the empirical test settles it | If shell +normal = OUTWARD (typical OML) and gauge pressure is positive → +1 multiplier compresses the body (correct). Verify with a single-shell test (`workflow/stage3_verify/_test_press_sign.inp`) when in doubt |
| 24 | **`.inp` re-import re-binds Pressure to SNEG** | A `Pressure` load that was originally on `side1Elements=` (SPOS) can come back from `ModelFromInputFile` bound to an *internal* surface `_M<N>` defined as `__M<N>_SNEG, SNEG` — the OPPOSITE side. The named `AERO_OML_SURF` may still exist on SPOS but the load doesn't use it | After re-import, dump the .inp via `Job.writeInput()` and grep for the load's region surface name — confirm `, SPOS` not `, SNEG`. Re-bind to the correct named surface (or flip `magnitude` sign) |
| 25 | **`loadStates[step][load_name]` is the source of truth for cf/cm values** | After `.inp` re-import, the load object's `getattr(L, 'cf1', ...)` returns `None` even though the analysis sees a value — the value lives on the per-step state, not the load creation kwargs | `m.steps[step].loadStates[load_name].cf1/cf2/cf3/cm1/cm2/cm3` (filter for `None` and `UNSET`). Use this when consolidating or summing duplicate loads |
| 26 | **`*Cload`/`*Dsload` re-import splits per DOF** | One `ConcentratedForce(cf1=A, cf3=B)` from script becomes two separate `CFORCE-N` / `CFORCE-N+M` loads after `.inp` re-import — one per non-zero component | When consolidating, group by `region` tuple `(set_name, 'Assembly', ...)`, sum component-wise, recreate one load per region. See `workflow/stage2_loads/consolidate_finloads.py` |
| 27 | **`assembly.sets[name].referencePoints` empty after re-import** | An RP set created via `Set(referencePoints=...)` becomes a `*Nset` after `.inp` round-trip; `referencePoints` accessor returns an empty `Sequence`, not the RPs | Use `assembly.SetByBoolean(operation=UNION, sets=...)` to combine sets — entity-type agnostic — when you need a combined RP region |
| 28 | **`assembly.getMassProperties()` can hang in noGUI** | On some imported assemblies (notably ModelFromInputFile output) the call never returns; no exception, no output, the script just stops at that line and PowerShell eventually returns empty | Always wrap in `try/except` and provide a fallback (e.g., compute CG from a known per-load IR ratio: `arm = thrust_IRM2 / cf3` gives `x_cg = x_engine + arm`). Or skip CG fetch entirely when not strictly needed |
| 29 | **`createStepName` is NOT on `ConcentratedForce`/`Moment`/`Pressure`** | Only `Gravity` exposes `createStepName` as an attribute. `getattr(L, 'createStepName')` raises `AttributeError` on the others — a try/except with `getattr(..., None)` default still raises because the AttributeError comes from descriptor access, not missing attribute | Hardcode the step name (`'MaxN'`) or read it from `L.createStepName` only after checking `type(L).__name__ == 'Gravity'`. For per-step values use `m.steps[step].loadStates[load_name]` regardless of load type |
| 30 | **Internal surfaces `_M<N>` are NOT in `assembly.surfaces`** | After ModelFromInputFile, a Pressure load's `region` may reference an internal surface name like `_M104`. The named user-facing surface (`AERO_OML_SURF`) still exists, but the load is bound to the internal one. `assembly.surfaces['_M104']` raises KeyError | When cloning such a load, fall back to the equivalent named surface: `if name.startswith('_M') and 'AERO_OML_SURF' in asm.surfaces: return asm.surfaces['AERO_OML_SURF']`. **Caveat:** this changes the SPOS/SNEG side binding — see #24, may need magnitude flip |
| 31 | **DiscField pressure cloned to a different surface gives wrong IR** | A `Pressure` load with `distributionType=DISCRETE_FIELD` is bound to specific elements. Cloning it onto a *different* surface (even covering the same elements) produces measurably different IRF/IRM than the original — observed ~5–15% deviation in the project. The cause is element-side or per-element field-value rebinding | For trim-critical analysis, do NOT use clone-based per-load decomposition with DiscFields. Use `load.suppress()` directly on the original load (see patterns §19). Trim diagnostics built on cloning will be wrong by the AeroPressure clone error |
| 32 | **`__file__` is undefined in Abaqus CAE noGUI** | Scripts run via `abaqus cae noGUI=script.py` are loaded with `execfile`, which does not set `__file__`. Any `os.path.dirname(__file__)` raises `NameError` | Use `os.getcwd()` (working directory is set to where you invoked abaqus) or hardcode a known relative path like `os.path.join(os.getcwd(), 'workflow', 'stage3_verify')` |
| 33 | **CAE GUI silently mutates the .cae mid-session** | If the user has the .cae open in CAE GUI while you run noGUI scripts, they may edit load values (or material/section properties) directly. Each `openMdb` reads disk state at-that-moment, so consecutive script runs can return different physics results without any code change. License manager will report `<0 out of 2 licenses available>` to confirm GUI is open | Always dump current load magnitudes (`m.steps[step].loadStates[name].cf3` etc.) at the START of any tuning script and print them. If results diverge between runs, ask the user whether they edited the model in GUI |
| 34 | **ODB version mismatch** | `openOdb()` raises `OdbError: The database is from a previous release of Abaqus` when the ODB was written by an older Abaqus version | Use the version-specific launcher matching the ODB origin: `abq2024 python script.py` or `abq2024 cae noGUI=script.py`. Alternatively upgrade: `abaqus -upgrade -job new_name -odb old_name` (creates a new file) |
| 35 | **`# -*- coding: mbcs -*-` causes SyntaxError** | On some Abaqus/Windows configurations, the `mbcs` codec fails to decode the BOM or certain byte sequences: `SyntaxError: 'mbcs' codec can't decode bytes in position 0--1` | Use `# -*- coding: utf-8 -*-` instead. Works on both Abaqus 2024 and 2025 |
| 36 | **`print()` output lost in PowerShell capture** | `abaqus cae noGUI=script.py` stdout is buffered by the Abaqus launcher; PowerShell frequently receives empty output even on successful runs | Write results to a file inside the script (`with open(path, 'w') as f: ...`) and read it back with `Read` or `Get-Content`. Never rely on captured stdout for ODB extraction results |

## Imports Cheatsheet

```python
# -*- coding: utf-8 -*-        # NOT mbcs - see gotcha #35
from abaqus import *
from abaqusConstants import *
import regionToolset
from caeModules import *   # REQUIRED for Equation/Coupling/Tie in noGUI
import math
import sys
```

For ODB postprocessing only (run via `abaqus python script.py`, no CAE):

```python
from odbAccess import openOdb
```

## Invocation Patterns

| Mode | Command | Use case | Reads `.cae`? | Reads `.odb`? |
|------|---------|----------|---------------|---------------|
| noGUI script | `abaqus cae noGUI=script.py` | Build models, modify, submit | yes | yes |
| With args | `abaqus cae noGUI=script.py -- arg1 arg2` | Parameterized scripts (`sys.argv[2:]`) | yes | yes |
| Python only | `abaqus python script.py` | Postprocess `.odb` (no GUI overhead) | no | yes |
| Plain Python | `python script.py` (your own Python env) | Pure helpers (parsing JSON, math) | no | no |

The `--` separator is mandatory when passing args; Abaqus consumes
everything before it. Inside the script, `sys.argv[0]` is the script
name and your args start at `sys.argv[1:]` for `noGUI`, but on some
configurations index shifts — print `sys.argv` to confirm.

## Cookbook — Minimal Working Snippets

### Open / save Mdb

```python
from abaqus import *
mdb = openMdb(pathName='D:/path/to/your/model.cae')
# ... do work ...
mdb.save()                                     # overwrite original
# mdb.saveAs(pathName='D:/backup/file_v2.cae')  # save copy
```

### New / copy / rename / delete model

```python
mdb.Model(name='Empty')                                          # new empty
mdb.Model(name='Copy', objectToCopy=mdb.models['Source'])        # deep copy
mdb.models.changeKey(fromName='OldName', toName='NewName')       # rename
del mdb.models['Unwanted']                                       # delete
```

### Find the last analysis step

```python
step_name = list(model.steps.keys())[-1]   # 'Initial' is index 0
```

### Promote a part-level set to assembly (element + node separately)

```python
assembly = model.rootAssembly
inst = assembly.instances['PART-1-1']
part = inst.part

part_set = part.sets['Skin_FinBase']

if len(part_set.elements) > 0:
    labels = [e.label for e in part_set.elements]
    assembly.Set(name='Skin_FinBase',
                 elements=inst.elements.sequenceFromLabels(labels))

if len(part_set.nodes) > 0:
    labels = [n.label for n in part_set.nodes]
    assembly.Set(name='Skin_FinBase_Node',
                 nodes=inst.nodes.sequenceFromLabels(labels))
```

### Reference point (with the comma gotcha)

```python
feat = assembly.ReferencePoint(point=(6374.1, 853.3, 0.0))
rp_id = feat.id                               # integer key
rp = assembly.referencePoints[rp_id]          # lightweight handle

assembly.Set(name='FinCP_2_Set',
             referencePoints=(rp,))           # NOTE the trailing comma
```

### Find an existing RP within tolerance (avoid duplicates)

Copy `find_existing_rp(assembly, x, y, z, tolerance)` from
`scripts/script_template.py` — it returns the key of the *nearest* live RP
within tolerance (skipping datum points and orphan features), or `None`.
Don't re-implement it per script.

### Surface from element set (positive normal)

```python
fin_set = assembly.sets['FinBase_2']
assembly.Surface(name='FinBase_2_Surf',
                 side1Elements=fin_set.elements)
```

### Distributing coupling (RP → surface) — most common

```python
model.Coupling(
    name='FinCoupling_2',
    controlPoint=regionToolset.Region(
        referencePoints=(assembly.referencePoints[rp_id],)),
    surface=assembly.surfaces['FinBase_2_Surf'],
    couplingType=DISTRIBUTING,
    influenceRadius=WHOLE_SURFACE,
    localCsys=None,
    u1=ON, u2=ON, u3=ON, ur1=ON, ur2=ON, ur3=ON,
    weightingMethod=UNIFORM,
)
```

### Kinematic coupling (rigid joint)

```python
model.Coupling(
    name='RigidJoint',
    controlPoint=regionToolset.Region(
        referencePoints=(assembly.referencePoints[rp_id],)),
    surface=assembly.surfaces['Slave_Surf'],
    couplingType=KINEMATIC,
    influenceRadius=WHOLE_SURFACE,
    u1=ON, u2=ON, u3=ON, ur1=ON, ur2=ON, ur3=ON,
)
```

`weightingMethod` is ignored when KINEMATIC. For DISTRIBUTING, all
translational DOFs must be ON.

### Concentrated force on RP set

```python
model.ConcentratedForce(
    name='FinLoad_2',
    createStepName=step_name,
    region=assembly.sets['FinCP_2_Set'],
    cf1=fx, cf2=fy, cf3=fz,
    distributionType=UNIFORM,
    follower=ON,                 # rotates with node frame; use only in nonlinear steps
    localCsys=None,
)
```

### Moment on RP set

```python
model.Moment(
    name='SectionMoment',
    createStepName=step_name,
    region=assembly.sets['FwdRP_Set'],
    cm1=0.0, cm2=bending_nmm, cm3=0.0,   # convert N·m → N·mm before passing
    distributionType=UNIFORM,
)
```

### Pressure load (uniform)

```python
model.Pressure(
    name='AeroPressure',
    createStepName=step_name,
    region=assembly.surfaces['OML_Surf'],
    magnitude=100.0,                 # MPa in mm-N-tonne
    distributionType=UNIFORM,
)
```

### Pressure load (mapped field from CFD)

```python
model.MappedField(
    name='AeroField',
    description='CFD gauge pressure',
    regionType=POINT,
    pointDataFormat=XYZ,
    fieldDataType=SCALAR,
    xyzPointData=(),                 # supply via file, see Abaqus docs
    localCsys=None,
)
model.Pressure(
    name='AeroPressure',
    createStepName=step_name,
    region=assembly.surfaces['OML_Surf'],
    distributionType=FIELD,
    field='AeroField',
    magnitude=1.0,                   # scale (sign-flippable)
)
```

### Gravity load

```python
model.Gravity(
    name='Gravity',
    createStepName=step_name,
    comp1=-9806.65,                  # mm/s² in mm-N-tonne (= 1 g)
    distributionType=UNIFORM,
)
```

### Inertia relief (pin all 6 DOFs)

```python
model.InertiaRelief(
    name='IR',
    createStepName=step_name,
    u1=1, u2=1, u3=1, ur1=1, ur2=1, ur3=1,
)
```

### Point mass at RP (assembly engineering features)

```python
assembly.engineeringFeatures.PointMassInertia(
    name='Inertia_Fin',
    region=regionToolset.Region(
        referencePoints=tuple(assembly.referencePoints[k] for k in rp_keys)),
    mass=0.01716,                    # tonne — written *per RP* by Abaqus
    alpha=0.0, composite=0.0,
)
```

When `region` contains N RPs, Abaqus writes N MASS elements each at the
given magnitude. Pre-divide if you have a *total* mass.

### Non-structural mass on a part-level set

```python
part = assembly.instances['PART-1-1'].part
part.engineeringFeatures.NonstructuralMass(
    name='Inertia_EngineNSM',
    region=part.sets['Engine'],
    units=TOTAL_MASS,                  # or MASS_PER_AREA, MASS_PER_LENGTH
    magnitude=0.17657,                 # tonne (total)
    distribution=MASS_PROPORTIONAL,
)
```

### Equation constraint (cylindrical CSYS)

```python
# csys_id from a Datum csys feature you created earlier
model.Equation(
    name='Eq_R_pair_1',
    terms=((1.0, 'EqN_pair_1_A1', 1, csys_id),
           (-1.0, 'EqN_pair_1_B1', 1, csys_id)),
)
```

DOF index 1=radial, 2=tangential, 3=axial in a cylindrical CSYS.

### Tie constraint

```python
model.Tie(
    name='Tie_1',
    master=assembly.surfaces['Master_Surf'],
    slave=assembly.surfaces['Slave_Surf'],
    positionTolerance=0.01,
    adjustMasterSurface=ON,
)
```

### Delete fin features in correct order

```python
for i in range(1, 5):
    if 'FinLoad_%d' % i in model.loads:
        del model.loads['FinLoad_%d' % i]
    if 'FinCoupling_%d' % i in model.constraints:
        del model.constraints['FinCoupling_%d' % i]
    if 'FinCP_%d_Set' % i in assembly.sets:
        del assembly.sets['FinCP_%d_Set' % i]
    if 'FinBase_%d_Surf' % i in assembly.surfaces:
        del assembly.surfaces['FinBase_%d_Surf' % i]
# RP features last; identify by coordinate or feature name
for name in list(assembly.features.keys()):
    if name.startswith('RP-') and assembly.features[name].xValue > 6300:
        del assembly.features[name]
```

### Submit a job and wait

```python
job = mdb.Job(
    name='MyJob',
    model='MyModel',
    type=ANALYSIS,
    numCpus=4, numDomains=4,
    memory=90, memoryUnits=PERCENTAGE,
)
job.submit(consistencyChecking=OFF)
job.waitForCompletion()
print('Job status: %s' % job.status)
# In abaqus cae noGUI mode, job.status often reads None even on success.
# Treat the .sta/.msg files as the truth source — look for
# "ANALYSIS HAS COMPLETED SUCCESSFULLY" in the .sta file.
```

### Read history output from an `.odb`

```python
from odbAccess import openOdb
odb = openOdb(path='MyJob.odb')
for step_name, step in odb.steps.items():
    for region in step.historyRegions.values():
        for var, ho in region.historyOutputs.items():
            last_value = ho.data[-1][1]      # (time, value) pairs
            print('%s -> %s = %.6e' % (step_name, var, last_value))
odb.close()
```

## `regionToolset.Region` vs `assembly.Set` — when to use which

Use `assembly.Set(...)` when:

- You will reference the region by name from another script.
- You need it to survive `assembly.regenerate()`.
- You need to inspect or delete it later by name.

Use `regionToolset.Region(...)` when:

- You're passing a region inline to a single API call (e.g.,
  `controlPoint=` of a coupling) and never need the name again.
- You want to combine entities ad hoc: `Region(nodes=..., referencePoints=...)`.

Both are valid for `controlPoint`, `surface`, `region` arguments. The
project's convention: persist named sets for fin RPs, engine RPs,
coupling targets — keep ad-hoc Regions only for one-call control points.

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

## Symbolic Constants Quick Reference

| Constant | Where used |
|----------|------------|
| `DISTRIBUTING`, `KINEMATIC`, `STRUCTURAL` | `model.Coupling(couplingType=...)` |
| `WHOLE_SURFACE` | `model.Coupling(influenceRadius=...)` |
| `UNIFORM`, `LINEAR`, `QUADRATIC`, `CUBIC` | `model.Coupling(weightingMethod=...)` |
| `UNIFORM`, `FIELD` | `model.ConcentratedForce(distributionType=...)`, `model.Pressure(...)` |
| `ON`, `OFF` | DOF flags, follower flag, adjust flags |
| `UNCHANGED`, `FREED` | `load.setValuesInStep(...)` |
| `TOTAL_MASS`, `MASS_PER_AREA`, `MASS_PER_LENGTH` | `NonstructuralMass(units=...)` |
| `MASS_PROPORTIONAL`, `VOLUME_PROPORTIONAL` | `NonstructuralMass(distribution=...)` |
| `ROTATIONAL_STRUCTURAL`, `ROTATIONAL_KINEMATIC` | `model.Coupling(rotationalCouplingType=...)` |
| `ANALYSIS`, `RESTART`, `RECOVER` | `mdb.Job(type=...)` |
| `STANDARD_EXPLICIT`, `ELECTROMAGNETIC` | `mdb.Model(modelType=...)` |
| `THREE_D`, `TWO_D_PLANAR`, `AXISYMMETRIC` | Part dimensionality |
| `DEFORMABLE_BODY`, `DISCRETE_RIGID_SURFACE`, `ANALYTIC_RIGID_SURFACE` | Part type |
| `XYZ`, `RTZ`, `RTP` | `MappedField(pointDataFormat=...)` |
| `SCALAR`, `VECTOR`, `TENSOR` | `MappedField(fieldDataType=...)` |
| `PERCENTAGE`, `MEGA_BYTES`, `GIGA_BYTES` | `Job(memoryUnits=...)` |

## Stringer & Skin (Shell Reinforcement)

Stringers are beam reinforcements on shell surfaces. **Requires
`from caeModules import *`** — without it, `part.stringers` raises
`AttributeError` even when stringers exist.

### Repository

```python
from caeModules import *
part.stringers                       # Repository of Stringer objects
part.stringers.keys()                # e.g. ['Stringer', 'Stringer-1', 'ringframe_1']
stringer = part.stringers['Stringer']
stringer.edges                       # EdgeArray — the geometry edges
stringer.elements                    # MeshElementArray — the meshed beam elements
```

### Create / edit / delete

```python
e = part.edges
edges = e.findAt(((x, y, z),))
part.Stringer(edges=edges, name='Stringer-1')       # create
part.EditStringer(edges=new_edges, name='Stringer')  # edit existing
del part.stringers['ringframe_1']                    # delete
```

### Beam section orientation on stringer edges

Use `part.Set(stringerEdges=...)` to create a persistent Set, then pass
it to `assignBeamSectionOrientation`. The first element of the tuple is
the **stringer name** from `part.stringers.keys()`.

```python
stringer = part.stringers['Stringer']
edges = stringer.edges

# Per angular group for radially-inward n1 on a cylinder:
region = part.Set(
    stringerEdges=(('Stringer', edges),),
    name='orient_set')
part.assignBeamSectionOrientation(
    region=region, method=N1_COSINES, n1=(0.0, -1.0, 0.0))
```

**Key points:**
- The stringer name in `stringerEdges` must match a key in `part.stringers`
- Use `part.Set(stringerEdges=...)` not `regionToolset.Region(stringerEdges=...)` —
  the Set form creates a persistent region
- To find edges for a given stringer, use `part.stringers['name'].edges`
  rather than searching through `sectionAssignments`

## API Path Quick Reference

```text
mdb                                  # Mdb (global, autoloaded by Abaqus CAE)
mdb.models['name']                   # Model
model.rootAssembly                   # Assembly (one per model)
assembly.instances['PART-1-1']       # PartInstance
inst.part                            # Part (back-reference)
inst.nodes[i]                        # MeshNode at index i (NOT label)
inst.nodes.sequenceFromLabels([...]) # MeshNodeArray from label list
inst.elements[i]                     # MeshElement at index i
elem.getNodes()                      # tuple of MeshNode (use .label)
assembly.sets['name']                # persistent Set
assembly.surfaces['name']            # persistent Surface
assembly.referencePoints[int_id]     # lightweight RP handle (no attrs)
assembly.features['RP-N']            # Feature (.xValue/.yValue/.zValue/.id)
assembly.engineeringFeatures.inertias['name']            # PointMassInertia
part.engineeringFeatures.nonstructuralMasses['name']     # NSM
part.stringers['name']               # Stringer (requires `from caeModules import *`)
part.skins['name']                   # Skin (same import requirement)
model.steps['Step-N']                # Step (StaticStep, BuckleStep, etc.)
model.constraints['name']            # Coupling / Tie / Equation / RigidBody
model.loads['name']                  # ConcentratedForce / Pressure / Gravity / Moment / ...
mdb.jobs['name']                     # Job
```
