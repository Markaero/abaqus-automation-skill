# -*- coding: utf-8 -*-
"""abqlib - categorized, idempotent helpers for Abaqus/CAE noGUI scripts.

Import from a noGUI script (``__file__`` is undefined there, so the kit
path comes from the User inputs block):

    import sys
    sys.path.insert(0, ABQLIB_PATH)   # .../abaqus-automation/scripts
    from abqlib import session, rp, sets, constraints, loads, bcs, mass

Every ``ensure_*`` function is idempotent: it deletes an existing object of
the same name and recreates it, so re-running a script gives the same model.
Functions take ``model`` / ``assembly`` / ``part`` explicitly - never rely on
the global ``mdb``.

Compatible with Abaqus Python 2.7 (<=2023) and 3.10 (2024+).
Catalog of every function: references/api_catalog.md
"""

__version__ = '0.1.0'
