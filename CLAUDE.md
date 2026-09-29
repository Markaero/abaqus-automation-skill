# abaqus-automation skill maintenance

Context for sessions that update this skill. Read before editing.

## Design Decisions

- **Generic core + project profiles**: API gotchas, patterns, and
  templates are generic; project-specific facts (CAE paths, model names)
  belong only in `references/projects.md`.
- **Five-step collaboration workflow**: inspect → write idempotent
  script → user confirms → noGUI execution → inspect to verify.
  Read-only operations run freely; mutations require user approval.
- **Parameterization = top "User Inputs" block**: all tunable values
  live at the script top. No config.py, no CLI arguments by default.
- **Categorized function library (`scripts/abqlib/`)**: one module per
  category (session, sets, rp, constraints, bcs, loads, mass, steps, job,
  odb, cleanup). Scripts import it via `SKILL_SCRIPTS_DIR` in User inputs
  (`__file__` is undefined in noGUI). `ensure_*` = delete-if-exists then
  create. Library modules never `from abaqus import *` (it shadows `sum`)
  and stay Py 2.7/3 compatible.
- **SKILL.md routes, the catalog lists**: SKILL.md maps requests to
  modules; `references/api_catalog.md` is generated from docstrings.

## Maintenance Rules

- New project / new CAE: **only edit `references/projects.md`**.
- New reusable operation: add a function to the right `scripts/abqlib/`
  module (docstring first line = catalog entry), a test in
  `tests/test_abqlib.py`, then `python3 tools/gen_catalog.py`. Add a
  routing row in SKILL.md only for a new category.
- New multi-step workflow: add to `references/patterns.md` with source and date.
- New API gotcha: add to `references/abaqus_api.md` gotcha table.
- `SKILL.md` stays generic — no project names or paths.
- New scripts start from `scripts/skill_template.py`.
- Before committing run `python3 tools/check_skill.py` and
  `python3 -m unittest discover -s tests` (plain Python 3, no Abaqus).
  The checker fails on mbcs headers, `sum(generator)`, `__file__`,
  f-strings/Py3-only syntax, gotcha numbering, and a stale catalog.
  The tests use fake Abaqus objects: they check abqlib logic, not that
  real Abaqus accepts the calls — smoke-test new functions in Abaqus.

## Known Design Choices

- Template encoding uses utf-8 (works on Abaqus 2024+; mbcs can cause
  SyntaxError on some configurations).
- WingsCrackTracer3 cohesive element workflow intentionally not catalogued;
  add when delamination analysis is needed.
