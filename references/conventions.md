# Project Conventions

The conventions you must follow when writing Abaqus automation scripts
for projects managed by this skill.

## Units (mm-N-tonne-s)

| Quantity | Unit | Notes |
|----------|------|-------|
| Length | mm | Coordinates, lengths, displacements |
| Force | N | Loads (cf1/cf2/cf3) |
| Mass | tonne | 1 tonne = 1000 kg; in `PointMassInertia.mass` and NSM `magnitude` |
| Time | s | |
| Stress / pressure | MPa | = N/mm²; `Pressure.magnitude` and stress output |
| Density | tonne/mm³ | Material density values |
| Acceleration | mm/s² | 1 g = 9806.65 mm/s²; `Gravity.comp1`, IRA history |
| Moment | N·mm | `Moment.cm1/cm2/cm3` — convert from N·m by ×1000 |

Aero values live in the script's "User inputs" block, stored in their
native units (N/m², m²) and converted at apply-time. If you add new
constants, follow the same pattern and document the conversion in a
comment. Project facts (which values, which model) are looked up in
`references/projects.md` — there is no shared config module.

## Project layout

```
your_project/
├── model.cae                       # the model database
├── workflow/
│   ├── stage0_cleanup/             # set/section nomenclature fixes
│   ├── stage1_build/               # model construction (build_models.py, masses)
│   ├── stage2_loads/               # aero/section/thrust/gravity application
│   └── stage3_verify/              # job submission & post (run_jobs_and_report.py)
├── calibration/                    # 3-phase density+force calibration loop
├── scripts/
│   ├── inspect/                    # read-only model inspection
│   └── fixes/                      # in-place model surgery
├── data/                           # reference inputs (CFD, mass spreadsheets)
├── docs/
│   ├── api-ref/                    # the Abaqus API reference (project-local)
│   ├── plans/                      # design plans
│   └── specs/                      # specs
├── archive/                        # legacy INPs and old scripts
├── Job_*.{inp,com,odb,dat,...}     # job artifacts at root
├── _*.log                          # script stdout logs at root
└── *_report.json                   # script JSON outputs at root
```

Top-level scripts (e.g., `apply_section_loads.py`) are the legacy flat
layout; new work should land under the appropriate `workflow/stageN_*`
directory when it fits.

## CAE / model identifiers

Define these in your `references/projects.md` per-project profile:

- **CAE path:** absolute path to the `.cae` file
- **Instance name:** the assembly instance (often `Part-1-1`)
- **Model names:** base model and any derived models

Derived models are typically built from a base model via
`mdb.Model(objectToCopy=...)` followed by geometry transforms
and feature recreation.

## Job naming

`Job_<config>_<loadcase>` — examples: `Job_Config1_Aero`, `Job_Config2_Static`,
`Job_thrust`. Each job emits `.inp / .com / .odb / .dat / .msg / .sta`
in the project root. ODB existence is the skip-if-done signal.

## Python interpreters

| Use case | Interpreter | Notes |
|----------|-------------|-------|
| Abaqus CAE scripts | `abaqus cae noGUI=script.py` | Abaqus 2024+ = embedded **Py 3.10**; 2023 and older = Py 2.7. Keep `# -*- coding: utf-8 -*-` and `%` formatting for cross-version portability; use `except Exception as ex:` (not the Py2 comma form) |
| ODB postprocessing | `abaqus python script.py` | Same embedded interpreter, no GUI overhead |
| ODB from older version | `abq2024 cae noGUI=script.py` or `abq2024 python script.py` | **ODB version must match reader** — use the version-specific launcher (e.g., `abq2024`) when the ODB was created by an older Abaqus release. Otherwise: `OdbError: The database is from a previous release` |
| Pure helpers (parsing, math) | Your conda/venv Python (e.g., `python3`) | Py 3.x; **never** Windows Store python shim |

**`from abaqus import *` shadows builtins.** It rebinds `sum` (and a
few others) to Abaqus symbols; passing a generator to `sum(...)`
raises `TypeError: arg1; found 'generator'`. Use a list comprehension
(`sum([x for x in it])`) or rename your local. This bites on both Py 2
and Py 3 Abaqus.

The conda env contains the project's third-party deps (`hyperx`, etc.).
The Windows Store `python` shim does nothing useful and breaks scripts.

## PowerShell capture quirks for `abaqus` calls

Windows PowerShell 5.1 wraps native command stderr in `ErrorRecord` objects.
For `abaqus` invocations:

- **Don't use a bare PowerShell `2>&1`** — the license-checkout banner goes
  to stderr, gets wrapped, and ends up clobbering stdout in the file. The
  `> _script.log 2>&1` form used elsewhere in this skill is for cmd/bash;
  from PowerShell run it through cmd:
  `cmd /c "abaqus cae noGUI=script.py > _script.log 2>&1"`, or just
  `abaqus cae noGUI=script.py | Out-Null`.
- Either way, the script writes its own report file (per "Reporting from
  inside Abaqus scripts" below) and that file is what you read back
  (`Get-Content`), never the captured stdout.
- **For ad-hoc inspection** of the Abaqus session log, read `abaqus.rpy`
  with `Get-Content abaqus.rpy -Tail 60` — the script's `print(...)` lines
  appear there as `#: <text>` (the replay-comment prefix).

For plot scripts that use only stdlib + a browser, run via your own
Python environment — **not** `abaqus python` — to avoid licensing
overhead and to use full Py 3 stdlib:

```powershell
& "path\to\your\python.exe" plot_section_forces.py results.csv
```

## File lock — close the CAE GUI before noGUI scripts

`openMdb(pathName=...)` will fail with "File open failed" + "0 out of
2 licenses available" if the same `.cae` is open in an interactive CAE
session. The lock is per-file, not per-process. Before running any
script that calls `openMdb` + `mdb.save()`, ask the user (or close
your own session) so the file is releasable. After the script runs, tell
the user to reopen the `.cae` (`File → Close`, then open) — an already
open GUI keeps showing its stale snapshot (API gotcha #22).

## Reporting from inside Abaqus scripts

`print(...)` to stdout is buffered by Abaqus's launcher and may be
truncated or appear out of order, especially for long runs. For
anything you need to read back reliably, write a sibling text/JSON
file next to the script and `print('Report: %s' % path)` at the end:

```python
REPORT_PATH = os.path.join(os.path.dirname(CAE_PATH),  # from the User inputs block
                           'workflow', 'stage1_build', '_my_script.txt')
f = open(REPORT_PATH, 'w'); f.write('\n'.join(lines)); f.close()
```

The `_<scriptname>.log` shell redirect still has its place (license
checkout, tracebacks), but the in-script written report is the
authoritative output for results-bearing scripts.

## Direct part access vs broken instances

If a CAE was built via `ModelFromInputFile` followed by `mdb.models[m].changeKey(...)`,
the resulting instance keeps a stale internal part-name reference and
`inst.part`, `inst.sets`, `inst.elements` will raise on access. Always
prefer:

```python
part = model.parts['PART-1']           # works, part itself is fine
labels = [e.label for e in part.sets['MY_SET'].elements]
```

over `model.rootAssembly.instances[INSTANCE].part`. For assembly-level
sets that need element labels, use `assembly.SetFromElementLabels(...)`
with the *instance name string* — it bypasses the broken traversal.

## `ModelFromInputFile` quirks

When you import a `.inp`:

- B31 connectivity is normalized to **lower-label-first**, undoing any
  manual node-order flip.
- All set / surface / elset / nset names are **uppercased**.
- The new instance may carry a stale internal part-name reference;
  see "Direct part access" above.

If you need to flip B31 orientation, do it via
`assignBeamSectionOrientation(method=N1_COSINES, n1=...)` per element,
not by editing `.inp` connectivity.

## Script invocation patterns

```bash
# Standard: run noGUI, capture stdout+stderr to a project-rooted log.
abaqus cae noGUI=apply_section_loads.py > _apply_loads.log 2>&1

# With args (note the -- separator):
abaqus cae noGUI=calibrate.py -- --cae model.cae --loads loads.json --mode full

# Pure Python helper:
python correction_calculator.py inputs.json
```

Log file naming is `_<scriptname>.log` (leading underscore so they sort
together). The log captures Abaqus license checkout + script `print()`
output. The `.rpy` (replay) file is Abaqus's session record; treat as
write-only — don't edit.

## Coding style for Abaqus scripts

```python
# -*- coding: utf-8 -*-
"""One-line purpose. Run: abaqus cae noGUI=this_script.py"""

from abaqus import *
from abaqusConstants import *
from caeModules import *           # for Equation/Coupling/Tie in noGUI
import regionToolset
import math
import sys

MODEL_NAME = 'My_Model'  # from the User inputs block; see references/projects.md


def my_step(model):
    """Verb-prefixed function name. Doctring of one line."""
    assembly = model.rootAssembly
    print('  Doing the thing on %s' % model.name)
    # ... work ...


# Main, comment/uncomment to select what runs (project convention)
mdb = openMdb(pathName=CAE_PATH)
model = mdb.models[MODEL_NAME]
my_step(model)
mdb.save()
print('Done.')
```

- `%` formatting (Py 2 compatible); no f-strings.
- Output via the template's `log()` helper (writes `REPORT_PATH`, echoes
  to stdout); no `logging` module.
- Functions take `model` (not `mdb`); the caller picks which model.
- Idempotent: every modifier checks `if name in container` before
  creating; uses `del` then recreate when shape may have changed.
- Save at end with `mdb.save()`. *Inspection scripts must not save.*

## Configuration & constants

Everything that has a magic value lives in the script's top "User
inputs" block (see `scripts/skill_template.py`), with a comment noting
the source (Excel cell, drawing, spec, calculation). Project facts
(CAE path, model names) are looked up in `references/projects.md` —
there is no shared config module. The `find_existing_rp(...)` helper
lives in `scripts/skill_template.py` — copy it into new scripts
(`# helper: copy from scripts/skill_template.py`) rather than
re-implementing.

## Reports

Results-bearing scripts emit a sibling `*.json` at the project root with
the headline numbers (`aero_job_report.json`, `diag_moments.json`,
`calibration_log.json`). Downstream tooling consumes the JSON, not the
script's stdout. Keep the JSON shape stable — break-safe key names,
floats not numpy types.

## Claude Code integration

If you use [Claude Code](https://claude.ai/code) with this skill,
configure allowed tools in your `.claude/settings.json` as needed.
No automated hooks are required.
