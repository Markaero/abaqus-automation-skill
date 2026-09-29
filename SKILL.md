---
name: abaqus-automation
description: Automate Abaqus/CAE Python scripting for finite-element analysis projects. Use whenever the user wants to create, modify, copy, or rotate Abaqus models, apply or change loads (concentrated forces, moments, pressure, gravity, mapped fields, thrust), define or edit boundary conditions, build couplings (DISTRIBUTING/KINEMATIC) or tie/equation constraints, manage reference points and assembly sets/surfaces, add point masses or non-structural masses, submit jobs and read .odb history outputs, inspect the model state (RPs, sets, loads, masses, constraints, steps), or run calibration/diagnostic loops. Triggers on requests mentioning: Abaqus, .cae files, .odb, .inp, noGUI scripts, abaqus cae, Mdb, mdb.Job, ConcentratedForce, Coupling, Pressure, Gravity, ReferencePoint, PointMassInertia, NonstructuralMass, Equation, Tie, aero loads, MaxQ, inertia relief, IRA/IRF/IRM, or any script that needs to be invoked via `abaqus cae noGUI=...`. Use even when the user only references a script filename, an RP, a load name, or asks to "check what's in the CAE".
---

# Abaqus Automation

## Overview

This skill makes you fluent in the project's Abaqus Python scripting
conventions so you can create models, apply loads and boundary
conditions, build couplings, manage masses, submit jobs, and inspect
state — first try, no API guesswork.

The project FEA scripts already implement most patterns; your job is to
**reuse them**, follow project conventions, and avoid the API gotchas
that silently produce wrong results (zero loads, flipped pressure,
stale regions, orphan RPs, KINEMATIC where DISTRIBUTING was intended).

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
1. Read the relevant reference file(s) below for the task at hand.
2. Reuse an existing project script when one fits — don't reinvent.
3. Follow conventions in references/conventions.md (units, naming,
   imports, idempotency).
4. Use scripts/skill_template.py as the starting boilerplate for any
   new noGUI script.
5. Use scripts/inspect_model.py before/after any non-trivial change
   to verify the model state.
```

## Collaboration Workflow (semi-automated modeling)

Default loop for every model-changing task. Read-only inspection runs
freely; anything that mutates a CAE goes through user confirmation.

1. **Inspect** — run `scripts/inspect_model.py` (or a task-specific
   read-only probe) to confirm current state. No confirmation needed.
2. **Write** — produce an idempotent script. All tunable values go in a
   top "User inputs" block (`scripts/skill_template.py` style). No
   config.py dependency.
3. **Confirm** — show the user the script (at minimum the User inputs
   block and what it will mutate) and wait for approval before running.
4. **Run** — `abaqus cae noGUI=<script>.py > _<script>.log 2>&1`, using
   the launcher matching the CAE version (see `references/projects.md`).
5. **Verify** — re-run the inspect step and diff the two JSON snapshots
   `inspect_model.py` writes (before vs after); report the diff to the
   user. Results go to a report/JSON file, never stdout-only. Remind the
   user to reopen the `.cae` if it is open in the GUI (it won't refresh).

## Bundled References

Load only what the task needs.

| File | When to read |
|------|--------------|
| `references/abaqus_api.md` | **Read this first** for any API call. Top 10 gotchas, cookbook snippets, symbolic constants, imports cheatsheet, invocation patterns. |
| `references/projects.md` | **Read before touching any CAE.** Per-project profiles: CAE paths, Abaqus version launchers, model/part/instance names, script pipelines, known caveats. |
| `references/patterns.md` | Read when you need to do something the project already does (fin loads, engine mass, equation constraints, calibration). Maps each task to the existing script that implements it. |
| `references/conventions.md` | Read when creating a new script: units (mm-N-tonne), file layout, naming, logging, JSON reports, coding style for Abaqus Python (2.7 on ≤2023, 3.10 on 2024+). |

## Bundled Scripts

Do not duplicate these — invoke or copy from them.

| File | Purpose |
|------|---------|
| `scripts/skill_template.py` | Boilerplate for new noGUI scripts — encoding header, standard imports, top "User inputs" block, report-file `log()`, `find_existing_rp` / `ensure_assembly_set` / `backup_cae` helpers, try/except main that never saves on failure. Copy this when creating a new script. |
| `scripts/inspect_model.py` | Read-only inspector. Run with `abaqus cae noGUI=inspect_model.py -- <cae_path> [model_name\|-] [report_path]`. Writes a text report + JSON snapshot (default `_inspect_<cae>.txt/.json` in cwd): steps, parts, sets, surfaces, RPs (with duplicate detection), constraints, loads with per-step values from `loadStates`, suppressed flags, masses. |

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

### "Apply a new load to an existing model"

1. Read `references/patterns.md` §5 (concentrated forces & moments).
2. Add the magnitude to the script's top "User inputs" block with a
   comment on its source.
3. Copy `scripts/skill_template.py` → `apply_<thing>.py` in the
   project's script directory (see `references/projects.md`).
4. Inside, after `openMdb`, find the right model and step (`get_last_step`).
5. Idempotent: delete the load if present, then `model.ConcentratedForce(...)`.
6. Show the user the User inputs block and what will change; after
   approval run `abaqus cae noGUI=apply_<thing>.py > _apply_<thing>.log 2>&1`.
7. Read the script's report file, then run `scripts/inspect_model.py`
   and diff against the pre-change snapshot.

### "Build a new derived model"

1. Read `references/patterns.md` §1 and §12 (model copy, fin feature
   delete order).
2. `mdb.Model(name='New', objectToCopy=mdb.models['Source'])` →
   `model.rootAssembly.regenerate()`.
3. If geometry changes (rotate / mirror), call `assembly.rotate(...)`.
4. Delete the features that must be rebuilt in order: loads,
   constraints, sets, surfaces, then RP features by coordinate.
5. Re-create features against the new geometry. Always look up RPs by
   coordinate, never by stored ID.

### "Submit a job and pull IR results"

1. Read `references/patterns.md` §10 and `references/abaqus_api.md`
   "Submit a job and wait" + "Read history output from an .odb".
2. `mdb.Job(name='Job_<config>_<loadcase>', model=name, type=ANALYSIS,
   numCpus=4, numDomains=4)` → `job.submit(consistencyChecking=OFF)` →
   `job.waitForCompletion()`.
3. Skip-if-done: `if os.path.exists('%s.odb' % job_name): ...`.
4. Open the `.odb` via `from odbAccess import openOdb` (this works in
   `abaqus cae noGUI=...` and `abaqus python ...`).
5. Pull last-frame `(time, value)` from `historyRegions[...].historyOutputs[var].data[-1][1]`.
6. Convert IRA from mm/s² to g (÷9806.65) for human-readable output.
7. Persist to `*_report.json`.

### "Read an existing ODB for post-processing"

1. Read `references/patterns.md` §24 for the full ODB extraction pattern.
2. **Match the Abaqus version** — if the ODB was created by Abaqus 2024,
   use `abq2024 cae noGUI=script.py` or `abq2024 python script.py`.
   Using the wrong version raises `OdbError: previous release`.
3. Use `# -*- coding: utf-8 -*-` (NOT `mbcs`) to avoid encoding errors.
4. **Always write results to a file** — `print()` stdout is unreliable
   in PowerShell capture. Use `with open(path, 'w') as f: f.write(...)`.
5. Open with `readOnly=True` to prevent accidental ODB corruption.
6. For history outputs (IRA/IRF/IRM, energy): iterate
   `odb.steps[step].historyRegions[region].historyOutputs`.
7. For field outputs (U, S, RF): use `odb.steps[step].frames[-1].fieldOutputs['S']`.
   Filter by set with `field.getSubset(region=odb.rootAssembly.elementSets['NAME'])`.

### "Check what's in the CAE"

1. Run `abaqus cae noGUI=<skill-path>/scripts/inspect_model.py -- <path/to/model.cae>`.
2. Read the report it writes (`_inspect_<cae>.txt` in cwd, plus a
   `.json` snapshot): steps, parts, sets, surfaces, RPs (duplicate
   detection at 10 mm), constraints, loads with per-step values,
   suppressed flags, masses.
3. It does **not** save the CAE — safe to run anytime (but the CAE must
   not be open in the GUI).

### "Add a non-structural mass"

1. Read `references/patterns.md` §8.
2. Decide: is it tied to discrete RPs, or distributed over an element
   set? RPs → `assembly.engineeringFeatures.PointMassInertia`. Element
   set → `part.engineeringFeatures.NonstructuralMass(units=TOTAL_MASS,
   distribution=MASS_PROPORTIONAL)`.
3. Add the magnitude (in tonne) to the User inputs block.
4. Idempotent: delete prior NSM with same name before recreating.

### "Build a one-shot standalone analysis (no project CAE)"

1. Read `references/abaqus_api.md` "Building a Model from Scratch" — covers
   sketch, part, material, section, mesh, assembly, step, BC, load.
2. Start from the auto-created `mdb` Abaqus provides at launch (the
   template's `openMdb` line is for existing-CAE work).
3. `os.chdir(...)` to your output dir before `job.submit()` so `.odb` and
   friends land where you want.
4. Skip `mdb.save()` for one-shot scripts; the .odb is the deliverable.
5. Don't trust `job.status` in noGUI-from-CAE mode — read `.sta`/`.msg`
   for the actual outcome.

### "Build coupling between an RP and a beam node ring"

1. Read `references/patterns.md` §4.
2. Promote the part-level beam elset to an assembly node set first
   (the project's `_Node`-suffix convention).
3. `model.Coupling(controlPoint=Region(referencePoints=(rp,)),
   surface=Region(nodes=node_set.nodes), couplingType=DISTRIBUTING,
   influenceRadius=WHOLE_SURFACE, rotationalCouplingType=ROTATIONAL_STRUCTURAL,
   ...)`.

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
