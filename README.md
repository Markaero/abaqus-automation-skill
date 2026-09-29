# Abaqus Automation — Claude Code Skill

A [Claude Code](https://claude.ai/code) skill that makes the AI assistant
fluent in Abaqus/CAE Python scripting. It bundles 36 documented API
gotchas, 29 reusable workflow patterns, a script template, and a
read-only model inspector — distilled from production finite-element
analysis work.

## Who This Is For

Engineers who use **Abaqus/CAE** and want Claude Code to write correct
noGUI scripts on the first try — without the usual API guesswork that
leads to silent errors (zero loads, flipped pressure, stale regions,
orphan RPs, wrong coupling types).

## Prerequisites

- [Claude Code](https://claude.ai/code) (CLI, desktop app, or IDE extension)
- Abaqus/CAE with a valid license (2024 or 2025 tested)

## Installation

Copy (or symlink) this folder into your Claude Code skills directory:

```
~/.claude/skills/abaqus-automation/
```

Claude Code automatically discovers skills in this directory. Once
installed, the skill activates whenever you mention Abaqus, `.cae`,
`.odb`, noGUI scripts, or any Abaqus API class in your prompt.

## What's Included

```
abaqus-automation/
├── SKILL.md                        # Main skill definition (Claude reads this)
├── CLAUDE.md                       # Maintenance guide for updating the skill
├── README.md                       # This file
├── .gitignore
├── references/
│   ├── abaqus_api.md               # 36 API gotchas + cookbook snippets
│   ├── patterns.md                 # 29 reusable workflow patterns
│   ├── conventions.md              # Project conventions (units, layout, style)
│   └── projects.md                 # Per-project profiles (customize this)
├── scripts/
│   ├── skill_template.py           # Boilerplate for new noGUI scripts
│   └── inspect_model.py            # Read-only CAE model inspector
└── tools/
    └── check_skill.py              # Consistency checks (plain Python 3)
```

## Key Features

### API Gotchas (36 documented traps)

The Abaqus Python API has many traps that don't raise errors — they
silently produce wrong results. This skill catalogs them so Claude
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

The skill enforces a safe, semi-automated workflow:

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

**`scripts/skill_template.py`** — Copy this when creating a new noGUI
script. Includes encoding header, standard imports, "User inputs" block,
report-file logging, `find_existing_rp` / `backup_cae` helpers, idempotent
patterns, and a try/except main that writes the traceback and never saves
a half-modified CAE.

### Maintaining the skill

Run `python3 tools/check_skill.py` before committing. It needs no Abaqus
and catches the skill contradicting its own gotchas (mbcs headers,
`sum(generator)`, `__file__`, gotcha numbering).

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

The skill reads this file before touching any CAE, so Claude knows which
launcher to use, what models exist, and what the instance is named.

### Adding New Patterns

When you develop a new reusable workflow, add it to
`references/patterns.md` with a code snippet. The skill will
automatically reference it in future sessions.

### Adding New Gotchas

When you discover a new API trap, add it to the gotcha table in
`references/abaqus_api.md`.

## Units

The skill defaults to the **mm-tonne-N-s** unit system:

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
