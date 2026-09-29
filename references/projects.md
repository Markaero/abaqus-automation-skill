# Project Profiles

One section per CAE. When adding a new project, only edit this file —
the other references stay generic.

All units follow the mm-tonne-N-s system (1 g = 9806.65 mm/s², stress
in MPa, density in tonne/mm³).

## Example Project

| Field | Value |
|-------|-------|
| Path | `D:\path\to\your\project\model.cae` |
| Launcher | `abaqus` (2025) or `abq2024` for older versions |
| Models | `Model-1` (base) → `Model-2` (derived) |
| Instance | `Part-1-1` |
| Scripts | `workflow/` pipeline or standalone scripts |

Notes:

- Derived models are typically built from a base model using
  `mdb.Model(objectToCopy=...)` followed by `assembly.rotate(...)` and
  feature deletion/recreation.
- New scripts use the "User inputs" block pattern
  (see `scripts/script_template.py`), not a shared config module.
- Scripts mutate the CAE in place (`openMdb` / `mdb.save()`).

## Adding a New Project

Copy the example above and fill in:

1. **Path**: absolute path to the `.cae` file.
2. **Launcher**: which `abaqus` / `abq20XX` command to use (must match
   the CAE version to avoid `OdbError: previous release`).
3. **Models**: list the model names inside the CAE and their relationships.
4. **Instance**: the assembly instance name (often `Part-1-1`).
5. **Scripts**: where the automation scripts live.
6. **Notes**: any project-specific caveats (version quirks, naming
   conventions, known issues).
