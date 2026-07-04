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

## Maintenance Rules

- New project / new CAE: **only edit `references/projects.md`**.
- New reusable pattern: add to `references/patterns.md` with source and date.
- New API gotcha: add to `references/abaqus_api.md` gotcha table.
- `SKILL.md` stays generic — no project names or paths.
- New scripts start from `scripts/skill_template.py`.

## Known Design Choices

- Template encoding uses utf-8 (works on Abaqus 2024+; mbcs can cause
  SyntaxError on some configurations).
- WingsCrackTracer3 cohesive element workflow intentionally not catalogued;
  add when delamination analysis is needed.
