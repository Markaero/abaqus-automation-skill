# Abaqus Automation — Agent Kit

An agent-neutral instruction kit that makes AI coding agents (Codex,
Cursor, GitHub Copilot, Gemini CLI, Claude Code, or your own agent)
fluent in Abaqus/CAE Python scripting. It bundles a categorized,
idempotent function library (`abqlib`), 36 documented API gotchas,
29 reusable workflow patterns, a script template, and a read-only
model inspector — distilled from production finite-element analysis
work.

## Who This Is For

Engineers who use **Abaqus/CAE** and want an AI agent to write correct
noGUI scripts on the first try — without the usual API guesswork that
leads to silent errors (zero loads, flipped pressure, stale regions,
orphan RPs, wrong coupling types).

## Prerequisites

- An AI agent that can read files and (ideally) run shell commands
- Abaqus/CAE with a valid license (2024 or 2025 tested; abqlib also
  targets the Python 2.7 of 2023 and older)

## Installation

Put this folder somewhere stable, e.g. `D:\tools\abaqus-automation`
(clone or copy). Everything the agent needs starts at **`AGENTS.md`**;
all paths inside it are relative to this folder. Then connect your agent:

| Agent | How |
|-------|-----|
| Any agent that reads `AGENTS.md` (Codex, Cursor, Copilot coding agent, …) | Add one line to your **project's** `AGENTS.md`: `For Abaqus/CAE work, read D:\tools\abaqus-automation\AGENTS.md and follow it.` |
| Agents with their own instructions file (Gemini CLI `GEMINI.md`, Copilot `.github/copilot-instructions.md`, Cursor rules, …) | Put the same line in that file. |
| Agents that support Agent Skills folders (`SKILL.md` with frontmatter, e.g. Claude Code) | Copy or symlink the folder into the agent's skills directory. `SKILL.md` only points to `AGENTS.md`. |
| Your own agent (SDK / API) | Load `AGENTS.md` into the system prompt (or give the agent a file-read tool and tell it to read it), plus a shell tool for `abaqus` commands. |

Then set `ABQLIB_PATH` in `scripts/script_template.py` to
`<kit folder>\scripts` so generated scripts can import `abqlib`.

No shell access or no Abaqus on the agent's machine? The agent still
writes the script and hands you the exact command to run; paste back
the report file it produces.

## What's Included

```
abaqus-automation/
├── AGENTS.md                       # Main instructions (all agents read this)
├── SKILL.md                        # Frontmatter shim for skill-aware agents -> AGENTS.md
├── CLAUDE.md                       # Shim -> AGENTS.md
├── README.md                       # This file
├── .gitignore
├── references/
│   ├── api_catalog.md              # abqlib functions by category (generated)
│   ├── abaqus_api.md               # 36 API gotchas + cookbook snippets
│   ├── patterns.md                 # 29 reusable workflow patterns
│   ├── conventions.md              # Project conventions (units, layout, style)
│   └── projects.md                 # Per-project profiles (customize this)
├── scripts/
│   ├── abqlib/                     # Categorized function library (import it)
│   ├── script_template.py          # Boilerplate for new noGUI scripts
│   └── inspect_model.py            # Read-only CAE model inspector
├── tools/
│   ├── check_consistency.py        # Consistency checks (plain Python 3)
│   └── gen_catalog.py              # Regenerates references/api_catalog.md
└── tests/                          # abqlib unit tests on fake Abaqus objects
```

## Key Features

### Categorized Function Library (`abqlib`)

The agent routes each request to a category and composes library calls
instead of writing raw API code every time:

| Module | Covers |
|--------|--------|
| `session` | open / backup / save CAE, copy models |
| `sets` | assembly sets, part→assembly promotion, surfaces, node sets by coordinate |
| `rp` | find-or-create reference points by coordinate, duplicates |
| `constraints` | DISTRIBUTING / KINEMATIC couplings, ties, equations, cylindrical csys |
| `bcs` | displacement BC, encastre |
| `loads` | force, moment, pressure, gravity, inertia relief, per-step values, suppress |
| `mass` | point masses (total auto-split per RP), non-structural mass |
| `steps` | static step, field / history outputs |
| `job` | submit + wait, skip-if-done, success from `.sta`, write `.inp` |
| `odb` | history values, IR summary (with g conversion), field max |
| `cleanup` | delete in the order Abaqus requires |

Every `ensure_*` is idempotent. Full signatures:
[`references/api_catalog.md`](references/api_catalog.md).

```python
from abqlib import rp, constraints, loads, mass
k = rp.ensure_rp(asm, (6374.1, 853.3, 0.0), set_name='Fin1_RP')
constraints.ensure_coupling(model, 'Fin1_Cpl', k, asm.surfaces['FinBase_1_Surf'])
loads.ensure_cforce(model, 'Fin1_Load', asm.sets['Fin1_RP'], (120.0, 0.0, 850.0))
mass.ensure_point_mass(asm, 'Fin_Mass', fin_keys, total_mass=0.0686)
```

### API Gotchas (36 documented traps)

The Abaqus Python API has many traps that don't raise errors — they
silently produce wrong results. This kit catalogs them so the agent
avoids them automatically:

- `inst.nodes[5]` is the 6th node, not label 5
- `assembly.ReferencePoint(...)` returns a Feature, not an RP
- Single-RP tuple needs trailing comma: `(rp,)` not `(rp)`
- `side1Elements` vs `side2Elements` flips pressure sign silently
- DISTRIBUTING (RBE3) vs KINEMATIC (RBE2) — different stiffness
- `model.Equation` / `Coupling` / `Tie` need `from caeModules import *`
- `PointMassInertia(mass=M)` writes M *per RP*, not total
- ... and 29 more

### Workflow Patterns (29 battle-tested recipes)

Each pattern is distilled from real production scripts with code snippets:

- Model copy / rename / derive
- Set & surface promotion (part → assembly)
- Reference point create / find / dedupe
- DISTRIBUTING vs KINEMATIC couplings
- Concentrated forces, moments, pressure (uniform & mapped field)
- Gravity, inertia relief, IR result extraction
- Point masses & non-structural masses
- Equation constraints (cylindrical pairing)
- Job submission & ODB post-processing
- Beam orientation (n2 inward on mixed-winding mesh)
- Section force extraction along an axis
- Calibration loops (density + force + trim)
- And more...

### Collaboration Workflow

The kit enforces a safe, semi-automated workflow:

1. **Inspect** — read-only probe to confirm current model state
2. **Write** — produce an idempotent script with tunable "User inputs" block
3. **Confirm** — show the user the script before running
4. **Run** — `abaqus cae noGUI=script.py`
5. **Verify** — re-inspect and report the diff

Read-only operations run freely. Anything that mutates a CAE requires
user confirmation first.

### Bundled Scripts

**`scripts/inspect_model.py`** — Run against any `.cae` to get a
structured report of steps, parts, sets, surfaces, reference points
(with duplicate detection), constraints, loads (per-step values from
`loadStates`, suppressed flags), and masses. It writes a text report and
a JSON snapshot; diff the snapshots from before and after a change to
verify it.

```bash
abaqus cae noGUI=inspect_model.py -- path/to/model.cae
abaqus cae noGUI=inspect_model.py -- path/to/model.cae ModelName
abaqus cae noGUI=inspect_model.py -- path/to/model.cae - out/_before.txt   # all models, custom path
```

**`scripts/script_template.py`** — Copy this when creating a new noGUI
script. Includes encoding header, standard imports, "User inputs" block,
report-file logging, `find_existing_rp` / `backup_cae` helpers, idempotent
patterns, and a try/except main that writes the traceback and never saves
a half-modified CAE.

### Maintaining the kit

Before committing:

```bash
python3 tools/gen_catalog.py              # after changing abqlib docstrings
python3 tools/check_consistency.py        # consistency + Py2.7 syntax + catalog freshness
python3 -m unittest discover -s tests     # abqlib logic on fake Abaqus objects
```

None of these need Abaqus. The tests check abqlib's logic, not that
Abaqus accepts the calls, so smoke-test new functions in a real CAE.

## Customization

### Adding Your Project

Edit `references/projects.md` to add a profile for your CAE:

```markdown
## My Project

| Field | Value |
|-------|-------|
| Path | `D:\path\to\my\project\model.cae` |
| Launcher | `abaqus` (2025) |
| Models | `Base_Model` → `Derived_Model` |
| Instance | `Part-1-1` |
| Scripts | `scripts/` |
```

The agent reads this file before touching any CAE, so it knows which
launcher to use, what models exist, and what the instance is named.

### Adding New Patterns

When you develop a new reusable workflow, add it to
`references/patterns.md` with a code snippet. Agents will
reference it in future sessions.

### Adding New Gotchas

When you discover a new API trap, add it to the gotcha table in
`references/abaqus_api.md`.

## Units

The kit defaults to the **mm-tonne-N-s** unit system:

| Quantity | Unit | Notes |
|----------|------|-------|
| Length | mm | Coordinates, displacements |
| Force | N | Load magnitudes |
| Mass | tonne | 1 tonne = 1000 kg |
| Stress | MPa | = N/mm² |
| Density | tonne/mm³ | Material density |
| Acceleration | mm/s² | 1 g = 9806.65 mm/s² |
| Moment | N·mm | Convert from N·m by ×1000 |

## License

MIT
