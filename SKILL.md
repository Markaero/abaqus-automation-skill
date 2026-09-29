---
name: abaqus-automation
description: Automate Abaqus/CAE Python scripting for finite-element analysis projects. Use whenever the user wants to create, modify, copy, or rotate Abaqus models, apply or change loads (concentrated forces, moments, pressure, gravity, mapped fields, thrust), define or edit boundary conditions, build couplings (DISTRIBUTING/KINEMATIC) or tie/equation constraints, manage reference points and assembly sets/surfaces, add point masses or non-structural masses, submit jobs and read .odb history outputs, inspect the model state (RPs, sets, loads, masses, constraints, steps), or run calibration/diagnostic loops. Triggers on requests mentioning: Abaqus, .cae files, .odb, .inp, noGUI scripts, abaqus cae, Mdb, mdb.Job, ConcentratedForce, Coupling, Pressure, Gravity, ReferencePoint, PointMassInertia, NonstructuralMass, Equation, Tie, aero loads, MaxQ, inertia relief, IRA/IRF/IRM, or any script that needs to be invoked via `abaqus cae noGUI=...`. Also triggers on Chinese requests such as 有限元, 建模, 加載荷, 邊界條件, 耦合, 參考點, 集中質量, 送出計算, 讀 ODB. Use even when the user only references a script filename, an RP, a load name, or asks to "check what's in the CAE".
---

# Abaqus Automation

## Overview

This skill makes you fluent in the project's Abaqus Python scripting
conventions so you can create models, apply loads and boundary
conditions, build couplings, manage masses, submit jobs, and inspect
state — first try, no API guesswork.

The bundled `abqlib` function library already implements the common
operations as idempotent, gotcha-safe calls; your job is to **route the
request to the right functions and compose them**, follow project
conventions, and avoid the API gotchas that silently produce wrong
results (zero loads, flipped pressure, stale regions, orphan RPs,
KINEMATIC where DISTRIBUTING was intended).

**Before writing or editing any Abaqus script, consult the bundled
references.** The Abaqus API has many traps that won't show up at
script-runtime — they only manifest as wrong numbers in the `.dat`.

## When to Use

Trigger this skill whenever the user wants to:

- **Build / modify a model** — new model, copy from existing, rotate
  instance, promote sets, split element sets, rebuild after a step
  change.
- **Apply or change loads** — `ConcentratedForce`, `Moment`, `Pressure`
  (uniform or `MappedField`), `Gravity`, `InertiaRelief`, follower
  flags, axial vs lateral load decomposition.
- **Define boundary conditions** — `DisplacementBC`, fixed RPs, ring
  constraints, equation pairing across rings.
- **Build couplings** — RP → finbase surface (DISTRIBUTING), RP → beam
  node ring (DISTRIBUTING + ROTATIONAL_STRUCTURAL), rigid joints
  (KINEMATIC).
- **Manage reference points** — create, find existing within tolerance,
  dedupe, delete in correct order.
- **Add masses** — `PointMassInertia` at RPs, `NonstructuralMass` on
  part-level sets.
- **Submit jobs / read ODBs** — `mdb.Job`, `waitForCompletion`,
  `odbAccess.openOdb`, history output extraction (IRA/IRF/IRM).
- **Inspect a CAE** — list models, sets, surfaces, RPs, loads,
  constraints, masses, steps; detect duplicate RPs; sanity-check
  configurations before a run.
- **Run calibration / diagnostic loops** — density scaling, force
  diagnostics, trim parameter computation.

Skip this skill only when the request has nothing to do with Abaqus
or finite-element analysis (e.g., pure data analysis on a CSV that
happens to contain stress numbers, or web UI work).

## How to Use This Skill

```text
1. Route the request with the table below -> which abqlib module(s).
2. If a "Must know" input is missing, ask (see "Clarify before writing").
3. Open references/api_catalog.md, pick functions, compose a script
   from scripts/skill_template.py. Write raw API calls only for what
   abqlib does not cover (use references/abaqus_api.md for those).
4. Follow the Collaboration Workflow: inspect -> write -> confirm -> run -> verify.
```

## Routing: request -> abqlib module

`scripts/abqlib/` is a categorized function library; every `ensure_*`
is idempotent. The signatures are in `references/api_catalog.md`
(generated from the code, so it is always current).

| User says (en / 中文) | Module | Typical calls | Must know |
|---|---|---|---|
| open / copy / save CAE, new derived model · 開檔、複製模型 | `session` | `open_cae`, `copy_model`, `save_cae` | CAE path, model names |
| set, surface, promote part set, node by coordinate · 建 set、surface | `sets` | `ensure_set`, `promote_part_set`, `ensure_surface`, `node_set_by_coords` | which elements/nodes, side for surfaces |
| reference point, RP, duplicate RPs · 參考點 | `rp` | `ensure_rp`, `find_rp`, `find_duplicate_rps` | coordinates (mm), tolerance |
| coupling, RBE2/RBE3, tie, equation, cylindrical csys · 耦合、綁定、方程式 | `constraints` | `ensure_coupling`, `ensure_tie`, `pair_equations`, `ensure_cylindrical_csys` | DISTRIBUTING vs KINEMATIC, shell surface vs beam ring |
| fix, support, encastre, prescribed displacement · 邊界條件、固定 | `bcs` | `ensure_displacement_bc`, `ensure_encastre` | region, which DOFs |
| force, moment, pressure, gravity, inertia relief, change load, suppress · 力、力矩、壓力、重力、慣性釋放 | `loads` | `ensure_cforce`, `ensure_moment`, `ensure_pressure`, `ensure_gravity`, `ensure_inertia_relief`, `set_load_values`, `suppress_all_but` | magnitude + units, direction/frame, step, pressure side |
| point mass, lumped mass, NSM · 集中質量、非結構質量 | `mass` | `ensure_point_mass` (takes TOTAL, splits per RP), `ensure_nsm` | total mass (tonne), which RPs/set |
| step, NLGEOM, field/history output · 分析步、輸出 | `steps` | `ensure_static_step`, `set_field_outputs`, `ensure_history_output` | step name, nlgeom (needed for follower loads) |
| run / submit job, write .inp · 送出計算 | `job` | `run_job`, `job_succeeded`, `write_input` | job name, cpus, work dir |
| results, ODB, IRA/IRF/IRM, max stress/displacement · 讀結果 | `odb` | `ir_summary`, `history_last_values`, `field_max` | ODB path, Abaqus version that wrote it |
| delete / clean up / rebuild features · 刪除、清理 | `cleanup` | `delete_in_order`, `delete_by_prefix` | names or prefix; RP coordinates |
| what's in the CAE? audit · 檢查模型 | `scripts/inspect_model.py` | run standalone (read-only) | CAE path |

Disambiguation:

| Request | If... | Use |
|---|---|---|
| "connect RP to the structure" | load spreading, no added stiffness | `ensure_coupling(kind='DISTRIBUTING')` |
| | rigid joint wanted | `ensure_coupling(kind='KINEMATIC')` |
| | target is a beam node ring | `ensure_coupling(..., beam_ring=True)` with `constraints.node_region` |
| "connect two meshes" | surfaces coincide, all DOFs | `ensure_tie` |
| | only some DOFs (e.g. radial) | `pair_equations` with a cylindrical csys |
| "add mass" | a few discrete points | `ensure_point_mass` (pass the TOTAL) |
| | smeared over an element set | `ensure_nsm` |
| "isolate one load's effect" | trim/IR diagnostics | `loads.suppress_all_but` + `job.run_job`, don't save the CAE |

## Clarify before writing

Ask instead of guessing when any of these is missing — wrong guesses
here produce plausible-looking but wrong results:

- **Units / frame** of every given number (N vs kN, N·m vs N·mm, global vs local csys).
- **Load direction and sign**, and for pressure, which side of the surface it acts on.
- **Total vs per-point** for masses and distributed forces.
- **Which model / step** when the CAE has several.
- **Coupling intent**: spread the load (DISTRIBUTING) or rigidly connect (KINEMATIC).
- **Save or not**: diagnostic runs (suppress, trial loads) should not save the CAE.

## Collaboration Workflow (semi-automated modeling)

Default loop for every model-changing task. Read-only inspection runs
freely; anything that mutates a CAE goes through user confirmation.

1. **Inspect** — run `scripts/inspect_model.py` (or a task-specific
   read-only probe) to confirm current state. No confirmation needed.
2. **Write** — compose abqlib calls in a copy of
   `scripts/skill_template.py`. All tunable values go in its top
   "User inputs" block. No config.py dependency.
3. **Confirm** — show the user the script (at minimum the User inputs
   block and what it will mutate) and wait for approval before running.
4. **Run** — `abaqus cae noGUI=<script>.py > _<script>.log 2>&1`, using
   the launcher matching the CAE version (see `references/projects.md`).
5. **Verify** — read the script's report file, re-run the inspect step
   and diff the two JSON snapshots `inspect_model.py` writes (before vs
   after); report the diff to the user. Remind the user to reopen the
   `.cae` if it is open in the GUI (it won't refresh).

Pre-run checklist (check before step 3):

- [ ] CAE is not open in the GUI; launcher matches the CAE/ODB version.
- [ ] Every number in User inputs has units and a source comment.
- [ ] Loads are in an analysis step (not `Initial`); follower loads have NLGEOM on.
- [ ] Point masses are passed as totals; gravity cases have density defined.
- [ ] Deletions go through `cleanup.delete_in_order` (loads → constraints → sets → RPs).
- [ ] Diagnostic scripts do not call `save_cae`.

## Bundled References

Load only what the task needs.

| File | When to read |
|------|--------------|
| `references/api_catalog.md` | **Read first when writing a script.** Every abqlib function by category with signature and one-line purpose. |
| `references/abaqus_api.md` | For raw API calls abqlib doesn't cover, and the full gotcha table (36 traps) with mitigations. |
| `references/projects.md` | **Read before touching any CAE.** Per-project profiles: CAE paths, Abaqus version launchers, model/part/instance names, script pipelines, known caveats. |
| `references/patterns.md` | Multi-step workflows proven in production (beam orientation, load consolidation after re-import, trim superposition, section forces, calibration). |
| `references/conventions.md` | Units, file layout, naming, logging, JSON reports, coding style for Abaqus Python (2.7 on ≤2023, 3.10 on 2024+). |

## Bundled Scripts

Do not duplicate these — import, invoke, or copy from them.

| File | Purpose |
|------|---------|
| `scripts/abqlib/` | Categorized function library (session, sets, rp, constraints, bcs, loads, mass, steps, job, odb, cleanup, util). Import after `sys.path.insert(0, SKILL_SCRIPTS_DIR)` — `__file__` is undefined in noGUI, so the path comes from the User inputs block. |
| `scripts/skill_template.py` | Starting point for every new noGUI script: User inputs block, abqlib import, `Report` file output, try/except main that writes the traceback and never saves on failure, CAE backup before save. |
| `scripts/inspect_model.py` | Read-only inspector, no abqlib dependency. `abaqus cae noGUI=inspect_model.py -- <cae_path> [model_name\|-] [report_path]`. Writes text + JSON snapshot (default `_inspect_<cae>.txt/.json` in cwd). |

## Project at a Glance

Units: **mm-tonne-N-s**. 1 g = 9806.65 mm/s². Stress in MPa, density in
tonne/mm³.

Per-project facts (CAE paths, Abaqus version launchers, model names,
instances, script pipelines) live in `references/projects.md` — read it
before touching any CAE.

Parameters convention: every tunable value lives in the script's top
"User inputs" block with a comment on its source. There is no shared
config module.

Key conventions:

- **Always consult API docs before writing Abaqus scripts** to avoid
  errors. The bundled `references/abaqus_api.md` is the curated form
  of those docs — use it before invoking any Abaqus class.
- **Use `from caeModules import *`** in noGUI scripts that build
  `model.Equation`, `model.Coupling`, or `model.Tie`.
- **Use a dedicated Python environment** for plain-Python helpers,
  not the Windows Store python shim.

## Top Gotchas (memorize these)

1. `inst.nodes[5]` is the 6th node, **not** node label 5.
2. `assembly.ReferencePoint(...)` returns a Feature; use `.id` to key
   into `assembly.referencePoints`.
3. Single-RP tuple needs the trailing comma: `(rp,)`.
4. `side1Elements` = positive normal; wrong side flips pressure sign
   silently.
5. Delete order: loads → constraints → sets/surfaces → RPs.
6. DISTRIBUTING (RBE3) ≠ KINEMATIC (RBE2). KINEMATIC adds rigid
   stiffness; DISTRIBUTING does not.
7. `model.Equation` / `Coupling` / `Tie` need `from caeModules import *`
   in noGUI scripts.
8. `regionToolset.Region(...)` is temporary and goes stale after
   `regenerate()`. Use `assembly.Set(...)` for anything you need to
   reference more than once.
9. `PointMassInertia(mass=M, region=N_RPs)` writes M *per RP*, not
   total. Pre-divide.
10. After `mdb.Model(objectToCopy=...)`, RP integer IDs may differ from
    the source — never hardcode IDs.

The full version with mitigations is in `references/abaqus_api.md`.

## Workflow Recipes (most common tasks)

All recipes start from a copy of `scripts/skill_template.py` and end
with the Collaboration Workflow's confirm → run → verify.

### "Apply a load at a point"

```python
k = rp.ensure_rp(asm, LOAD_POINT, tol=10.0, set_name='Thrust_RP')
constraints.ensure_coupling(model, 'Thrust_Cpl', k, asm.surfaces['Mount_Surf'])  # DISTRIBUTING
loads.ensure_cforce(model, 'Thrust', asm.sets['Thrust_RP'], (0.0, 0.0, THRUST_N))
```

For an existing load just change the value: `loads.set_load_values(model, 'Thrust', cf3=NEW)`.

### "Build a new derived model"

```python
model = session.copy_model(mdb, 'Base', 'Derived')        # regenerates; RP ids may change
model.rootAssembly.rotate(instanceList=(INST,), axisPoint=(0, 0, 0),
                          axisDirection=(1, 0, 0), angle=45.0)
cleanup.delete_in_order(model, loads=[...], constraints=[...], sets=[...],
                        surfaces=[...], rp_points=OLD_RP_COORDS)
# then rebuild features with ensure_* against the new geometry (RPs by coordinate)
```

### "Add masses"

```python
keys = [rp.ensure_rp(asm, p) for p in FIN_RP_COORDS]
mass.ensure_point_mass(asm, 'Fin_Mass', keys, total_mass=FIN_TOTAL_T)  # split per RP for you
mass.ensure_nsm(model.parts[PART], 'Payload_NSM', 'Payload', total_mass=PAYLOAD_T)
```

### "Submit a job and pull IR results"

```python
ok = job.run_job(mdb, 'Job_Cfg1_MaxQ', MODEL_NAME, work_dir=WORK_DIR)   # skip-if-done
if ok:
    report.data['ir'] = odb.ir_summary(os.path.join(WORK_DIR, 'Job_Cfg1_MaxQ.odb'))
```

`job.status` is unreliable in noGUI; `run_job` reads the `.sta` instead.
For ODB-only work run `abaqus python` with the launcher matching the ODB
version (`OdbError: previous release` otherwise); see `references/patterns.md` §24.

### "Isolate one load's contribution (diagnostic, no save)"

```python
off = loads.suppress_all_but(model, keep=['AeroPressure'])
job.run_job(mdb, 'Job_diag_aero', MODEL_NAME, skip_if_done=False)
loads.resume_loads(model, off)          # and do NOT call session.save_cae
```

Use suppress, not cloned loads, for DISCRETE_FIELD pressures (gotcha #31).

### "Check what's in the CAE"

1. Run `abaqus cae noGUI=<skill-path>/scripts/inspect_model.py -- <path/to/model.cae>`.
2. Read `_inspect_<cae>.txt` (and the `.json` snapshot): steps, parts,
   sets, surfaces, RPs with duplicate detection, constraints, loads with
   per-step values, suppressed flags, masses.
3. Read-only, safe anytime (but the CAE must not be open in the GUI).

### "Build a one-shot standalone analysis (no project CAE)"

1. Read `references/abaqus_api.md` "Building a Model from Scratch" for
   sketch, part, material, section, mesh (abqlib does not cover these yet).
2. Then use abqlib for the rest: `steps.ensure_static_step`,
   `bcs.ensure_encastre`, `loads.*`, `job.run_job(..., work_dir=...)`,
   `odb.field_max`.
3. Skip `save_cae` for one-shot scripts; the .odb is the deliverable.

## Common Mistakes

| Symptom | Cause | Fix |
|---------|-------|-----|
| `KeyError` on `assembly.referencePoints[id]` after copying a model | RP IDs renumber on copy/regenerate | Look up RPs by feature coords (`find_existing_rp` helper in `scripts/skill_template.py`) |
| Pressure pushes the wrong way | Positive `magnitude` pushes *against* the bound side's normal; the load may be on SNEG instead of SPOS (common after `.inp` re-import) | Check which side the load is bound to (`writeInput()` + grep `SPOS`/`SNEG`); rebind to the `side1Elements` surface or flip the sign. See API gotchas #6/#23/#24 |
| `model.Coupling` is undefined in noGUI script | Missing import | Add `from caeModules import *` |
| Tuple of one RP raises `TypeError` | Missing trailing comma | `referencePoints=(rp,)` |
| Total point mass is N× too large | `PointMassInertia` writes magnitude per RP | Divide total mass by N RPs before passing |
| Job submit fails on consistency check | Region went stale after regen | Replace ad-hoc Regions with persistent assembly Sets |
| `_<script>.log` shows license messages but nothing else | stdout lost/unflushed under noGUI | Read the script's `REPORT_PATH` file (the template writes tracebacks there); else check `abaqus.rpy` |
| `openMdb` fails with "File open failed" / "0 out of 2 licenses" | The `.cae` is open in the CAE GUI | Ask the user to close CAE, then rerun |
| `NameError: __file__` | noGUI runs scripts via `execfile` | Use `os.getcwd()` or an absolute path in User inputs |
| `TypeError: ... found 'generator'` | `from abaqus import *` shadows `sum` | `sum([... for ...])` |
| Equation constraint silently does nothing | Wrong CSYS id, or DOF index off (radial vs axial) | DOF 1=radial, 2=tangential, 3=axial in cylindrical CSYS |

## What This Skill Does Not Cover

- Heavy mesh generation, partitioning, and CAD prep are upstream of this
  skill (handled in NX/SpaceClaim and pre-built into the project CAE).
  Simple part/mesh creation for standalone analysis scripts IS covered —
  see `references/abaqus_api.md` "Building a Model from Scratch".
- Material database or composite layup definitions (usually owned by a
  separate sizing tool/skill).
- Pre-CAE CAD operations (handled upstream by the user in NX/SpaceClaim).

If a request lands in those areas, fall back to the project's own
Abaqus documentation (if `references/projects.md` lists one) or ask the
user.
