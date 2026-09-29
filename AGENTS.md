
# Abaqus Automation — Agent Guide

Instructions for any coding agent (Codex, Cursor, Copilot, Gemini CLI,
Claude Code, custom agents) that writes or runs Abaqus/CAE Python
scripts. Paths below are relative to the directory containing this file
(the "kit directory"); resolve them against that directory, not the
user's project.

## Overview

This guide makes you fluent in the project's Abaqus Python scripting
conventions so you can create models, apply loads and boundary
conditions, build couplings, manage masses, submit jobs, and inspect
state — first try, no API guesswork.

The bundled `abqlib` function library already implements the common
operations as idempotent calls; your job is to **route the request to the
right functions and compose them**, and to **look up every other API
call before you use it** (`tools/api_lookup.py`). Most scripting mistakes
are documented behavior that nobody looked up; they rarely raise errors
and only show up as wrong numbers in the `.dat` (zero loads, flipped
pressure, masses N× too large).

## When to Use

Follow this guide whenever the user wants to:

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

Skip this guide only when the request has nothing to do with Abaqus
or finite-element analysis (e.g., pure data analysis on a CSV that
happens to contain stress numbers, or web UI work).

## How to Use This Guide

```text
1. Route the request with the table below -> which abqlib module(s).
2. If a "Must know" input is missing, ask (see "Clarify before writing").
3. Open references/api_catalog.md, pick functions, compose a script
   from scripts/script_template.py. For anything abqlib does not cover,
   look the call up first (tools/api_lookup.py, matching the Abaqus
   version) and check references/abaqus_api.md for undocumented traps.
4. Follow the Collaboration Workflow: inspect -> write -> confirm -> run -> verify.
```

## Routing: request -> abqlib module

`scripts/abqlib/` is a categorized function library; every `ensure_*`
is idempotent. The signatures are in `references/api_catalog.md`
(generated from the code, so it is always current).

| User says (en / 中文) | Module | Typical calls | Must know |
|---|---|---|---|
| open / copy / save CAE, new derived model · 開檔、複製模型 | `cae` | `open_cae`, `copy_model`, `save_cae` | CAE path, model names |
| set, surface, promote part set, node by coordinate · 建 set、surface | `sets` | `ensure_set`, `promote_part_set`, `ensure_surface`, `node_set_by_coords` | which elements/nodes, side for surfaces |
| reference point, RP, duplicate RPs · 參考點 | `rp` | `ensure_rp`, `find_rp`, `find_duplicate_rps` | coordinates (mm), tolerance |
| coupling, RBE2/RBE3, tie, equation, cylindrical csys · 耦合、綁定、方程式 | `constraints` | `ensure_coupling`, `ensure_tie`, `pair_equations`, `ensure_cylindrical_csys` | DISTRIBUTING vs KINEMATIC, shell surface vs beam ring |
| fix, support, encastre, prescribed displacement · 邊界條件、固定 | `bcs` | `ensure_displacement_bc`, `ensure_encastre` | region, which DOFs |
| force, moment, pressure, gravity, inertia relief, change load, suppress · 力、力矩、壓力、重力、慣性釋放 | `loads` | `ensure_cforce`, `ensure_moment`, `ensure_pressure`, `ensure_gravity`, `ensure_inertia_relief`, `set_load_values`, `suppress_all_but` | magnitude + units, direction/frame, step, pressure side |
| point mass, lumped mass, NSM · 集中質量、非結構質量 | `mass` | `ensure_point_mass` (takes TOTAL, splits per RP), `ensure_nsm` | total mass (tonne), which RPs/set |
| step, NLGEOM, field/history output · 分析步、輸出 | `steps` | `ensure_static_step`, `set_field_outputs`, `ensure_history_output` | step name, nlgeom (needed for follower loads) |
| run / submit job, write .inp · 送出計算 | `jobs` | `run_job`, `job_succeeded`, `write_input` | job name, cpus, work dir |
| results, ODB, IRA/IRF/IRM, max stress/displacement · 讀結果 | `results` | `ir_summary`, `history_last_values`, `field_max` | ODB path, Abaqus version that wrote it |
| delete / clean up / rebuild features · 刪除、清理 | `cleanup` | `delete_in_order`, `delete_by_prefix` | names or prefix; RP coordinates |
| what's in the CAE? audit · 檢查模型 | `scripts/inspect_model.py` | run standalone (read-only) | CAE path |
| how do I call X / what does X return / which arguments · API 怎麼用 | `tools/api_lookup.py` | `python3 tools/api_lookup.py <Name>` | Abaqus version |

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
| "isolate one load's effect" | trim/IR diagnostics | `loads.suppress_all_but` + `jobs.run_job`, don't save the CAE |

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
   `scripts/script_template.py`. All tunable values go in its top
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
- [ ] Every Abaqus call that abqlib doesn't wrap was looked up for this Abaqus version.
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
| `references/abaqus_api.md` | How to look up the API, the 23 traps the docs don't mention (grouped: every run / imported `.inp` models / beam orientation / empirical), and building a model from scratch. |
| `references/projects.md` | **Read before touching any CAE.** Per-project profiles: CAE paths, Abaqus version launchers, model/part/instance names, script pipelines, known caveats. |
| `references/patterns.md` | 7 multi-step workflows abqlib doesn't cover (beam orientation, beams in a shell footprint, load consolidation after re-import, pressure-direction check, wire features, definition transfer, parametric modeling). |
| `references/conventions.md` | Units, file layout, naming, logging, JSON reports, coding style for Abaqus Python (2.7 on ≤2023, 3.10 on 2024+). |

## Bundled Scripts

Do not duplicate these — import, invoke, or copy from them.

| File | Purpose |
|------|---------|
| `scripts/abqlib/` | Categorized function library (cae, sets, rp, constraints, bcs, loads, mass, steps, jobs, results, cleanup, util). Import after `sys.path.insert(0, ABQLIB_PATH)` — `__file__` is undefined in noGUI, so the path comes from the User inputs block. |
| `scripts/script_template.py` | Starting point for every new noGUI script: User inputs block, abqlib import, `Report` file output, try/except main that writes the traceback and never saves on failure, CAE backup before save. |
| `tools/api_lookup.py` | Offline API lookup from abqpy stubs (plain Python 3.9+): signature, argument docs, class members, "accessed by" path, version notes. One-time setup in `references/abaqus_api.md`. |
| `scripts/inspect_model.py` | Read-only inspector, no abqlib dependency. `abaqus cae noGUI=inspect_model.py -- <cae_path> [model_name\|-] [report_path]`. Writes text + JSON snapshot (default `_inspect_<cae>.txt/.json` in cwd). |

## Agent Capability Notes

This guide assumes only that you can read files and run shell commands.

- **No shell access / Abaqus not installed where you run?** Still write
  the script, then give the user the exact command to run
  (`abaqus cae noGUI=<script>.py > _<script>.log 2>&1`) and ask them to
  paste back the report file it writes. Never claim a run you did not do.
- **Confirmation** (Collaboration Workflow step 3) means stopping and
  waiting for the user's reply in the conversation — no special tool is
  required. Read-only inspection never needs confirmation.
- **Loading references:** read only the files the routing table points
  to; `references/api_catalog.md` is short, the others are long.
- Abaqus usually runs on Windows; expect PowerShell and read
  `references/conventions.md` "PowerShell capture quirks".

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

- **Look up, don't guess**: read the docs for every Abaqus call abqlib
  doesn't wrap (`tools/api_lookup.py`). `references/abaqus_api.md` lists
  only what the docs don't say.
- **Use a dedicated Python environment** for plain-Python helpers,
  not the Windows Store python shim.

## Traps the Docs Won't Warn You About

These hold for every run; the full list (imported models, beam
orientation, empirical findings) is in `references/abaqus_api.md`.

1. stdout is lost under noGUI/PowerShell — results go to a report file
   (the template does this).
2. The CAE must be closed in the GUI before a script opens it, and the
   GUI won't show a script's changes until the file is reopened.
3. No `__file__`, unreliable argv — paths and inputs come from the User
   inputs block.
4. `# -*- coding: utf-8 -*-`, never `mbcs`.
5. After `from abaqus import *`, `sum()` rejects generators — use a list.
6. Read an ODB with the launcher of the Abaqus version that wrote it.

## Workflow Recipes (most common tasks)

All recipes start from a copy of `scripts/script_template.py` and end
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
model = cae.copy_model(mdb, 'Base', 'Derived')            # regenerates; RP ids may change
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
ok = jobs.run_job(mdb, 'Job_Cfg1_MaxQ', MODEL_NAME, work_dir=WORK_DIR)  # skip-if-done
if ok:
    report.data['ir'] = results.ir_summary(os.path.join(WORK_DIR, 'Job_Cfg1_MaxQ.odb'))
```

`job.status` is unreliable in noGUI; `run_job` reads the `.sta` instead.
For ODB-only work run `abaqus python` with the launcher matching the ODB
version (API trap #10).

### "Isolate one load's contribution (diagnostic, no save)"

```python
off = loads.suppress_all_but(model, keep=['AeroPressure'])
jobs.run_job(mdb, 'Job_diag_aero', MODEL_NAME, skip_if_done=False)
loads.resume_loads(model, off)          # and do NOT call cae.save_cae
```

Use suppress, not cloned loads, for DISCRETE_FIELD pressures (API trap #22).

### "Check what's in the CAE"

1. Run `abaqus cae noGUI=<kit-dir>/scripts/inspect_model.py -- <path/to/model.cae>`.
2. Read `_inspect_<cae>.txt` (and the `.json` snapshot): steps, parts,
   sets, surfaces, RPs with duplicate detection, constraints, loads with
   per-step values, suppressed flags, masses.
3. Read-only, safe anytime (but the CAE must not be open in the GUI).

### "Build a one-shot standalone analysis (no project CAE)"

1. Read `references/abaqus_api.md` "Building a Model from Scratch" for
   sketch, part, material, section, mesh (abqlib does not cover these yet).
2. Then use abqlib for the rest: `steps.ensure_static_step`,
   `bcs.ensure_encastre`, `loads.*`, `jobs.run_job(..., work_dir=...)`,
   `results.field_max`.
3. Skip `save_cae` for one-shot scripts; the .odb is the deliverable.

## Common Mistakes

| Symptom | First move |
|---------|------------|
| Wrong numbers but no error (zero load, mass N× too large, flipped sign) | Look up the documented semantics of every call involved (`tools/api_lookup.py`) — e.g. a point mass applies to *each* point; load values live on `loadStates` |
| `AttributeError` / `KeyError` on an Abaqus object | Wrong member or repository name: look it up (e.g. NSMs are in `engineeringFeatures.inertias`; there is no `nonstructuralMasses`) |
| `TypeError` / keyword error on an argument | The argument may not exist in this Abaqus version — check `versionadded` in the lookup (e.g. `rotationalCouplingType` needs 2024+) |
| Pressure pushes the wrong way | API traps #15 and #21 (side binding, one-element test) |
| `_<script>.log` shows license messages but nothing else | API trap #1: read the script's report file; else `abaqus.rpy` |
| `openMdb` fails with "File open failed" / "0 out of 2 licenses" | API trap #6: the `.cae` is open in the GUI |
| `NameError: __file__` / `TypeError: ... found 'generator'` | API traps #3 / #5 |
| `OdbError: ... previous release` | API trap #10: use the matching launcher |

## What This Guide Does Not Cover

- Heavy mesh generation, partitioning, and CAD prep are upstream of this
  guide (handled in NX/SpaceClaim and pre-built into the project CAE).
  Simple part/mesh creation for standalone analysis scripts IS covered —
  see `references/abaqus_api.md` "Building a Model from Scratch".
- Material database or composite layup definitions (usually owned by a
  separate sizing tool).
- Pre-CAE CAD operations (handled upstream by the user in NX/SpaceClaim).

If a request lands in those areas, fall back to the project's own
Abaqus documentation (if `references/projects.md` lists one) or ask the
user.

## Maintaining This Kit

Only relevant when editing this repository itself.

### Design Decisions

- **Agent-neutral kit**: AGENTS.md is the single source of instructions;
  SKILL.md (Agent Skills frontmatter) and CLAUDE.md only point to it.

- **Generic core + project profiles**: API traps, patterns, and
  templates are generic; project-specific facts (CAE paths, model names)
  belong only in `references/projects.md`.
- **Five-step collaboration workflow**: inspect → write idempotent
  script → user confirms → noGUI execution → inspect to verify.
  Read-only operations run freely; mutations require user approval.
- **Parameterization = top "User Inputs" block**: all tunable values
  live at the script top. No config.py, no CLI arguments by default.
- **Categorized function library (`scripts/abqlib/`)**: one module per
  category (cae, sets, rp, constraints, bcs, loads, mass, steps, jobs,
  results, cleanup). Module names must not shadow Abaqus globals
  (`session`, the `job` module, the usual `odb` variable). Scripts import it via `ABQLIB_PATH` in User inputs
  (`__file__` is undefined in noGUI). `ensure_*` = delete-if-exists then
  create. Library modules never `from abaqus import *` (it shadows `sum`)
  and stay Py 2.7/3 compatible.
- **Docs first, traps second**: the kit does not restate the Abaqus API
  documentation. Agents look calls up (`tools/api_lookup.py`, abqpy stubs);
  `references/abaqus_api.md` holds only what the docs don't say.
- **AGENTS.md routes, the catalog lists**: AGENTS.md maps requests to
  modules; `references/api_catalog.md` is generated from docstrings.

### Rules

- New project / new CAE: **only edit `references/projects.md`**.
- New reusable operation: add a function to the right `scripts/abqlib/`
  module (docstring first line = catalog entry), a test in
  `tests/test_abqlib.py`, then `python3 tools/gen_catalog.py`. Add a
  routing row in AGENTS.md only for a new category.
- New multi-step workflow: add to `references/patterns.md` with source and date.
- New API trap: first check the docs (`tools/api_lookup.py`). If the docs
  state it, it is not a trap — don't add it. Otherwise add a row to the
  matching group in `references/abaqus_api.md` and renumber; the checker
  validates every `API trap #N` and `patterns §N` reference.
- Any new or changed Abaqus call in abqlib: verify arguments, members and
  `versionadded` with `tools/api_lookup.py` before committing.
- `AGENTS.md` stays generic — no project names or paths — and agent-neutral
  (no vendor-specific tools or file locations; per-agent setup goes in README).
- `SKILL.md` is only a frontmatter shim for skill-aware agents; keep its
  body a pointer to AGENTS.md.
- New scripts start from `scripts/script_template.py`.
- Before committing run `python3 tools/check_consistency.py` and
  `python3 -m unittest discover -s tests` (plain Python 3, no Abaqus).
  The checker fails on mbcs headers, `sum(generator)`, `__file__`,
  f-strings/Py3-only syntax, trap numbering, dangling trap/§ references,
  and a stale catalog.
  The tests use fake Abaqus objects: they check abqlib logic, not that
  real Abaqus accepts the calls — smoke-test new functions in Abaqus.

### Known Design Choices

- Template encoding uses utf-8 (works on Abaqus 2024+; mbcs can cause
  SyntaxError on some configurations).
- WingsCrackTracer3 cohesive element workflow intentionally not catalogued;
  add when delamination analysis is needed.
