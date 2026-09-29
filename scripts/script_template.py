# -*- coding: utf-8 -*-
"""Template for an Abaqus noGUI automation script built on abqlib.

Copy this file, rename it, edit the "User inputs" block and the step
function(s). Pick library calls from references/api_catalog.md.
Conventions:
- utf-8 encoding header (avoid mbcs, gotcha #35)
- every tunable value lives in the "User inputs" block - no config.py
- abqlib ensure_* calls are idempotent: re-running gives the same model
- results go to REPORT_PATH (text) + sibling .json; stdout is unreliable
- on any exception: traceback goes to the report and the CAE is NOT saved
- the CAE is backed up before mdb.save()

Run:  abaqus cae noGUI=this_script.py > _this_script.log 2>&1
      (use the launcher matching the CAE version, e.g. abq2024;
       from PowerShell wrap in: cmd /c "...")
"""

from abaqus import *
from abaqusConstants import *
from caeModules import *           # required for model.Equation/Coupling/Tie
import sys
import traceback

# ----------------------------------------------------------------------
# User inputs, unit = mm, N, tonne  (edit this block only)
# ----------------------------------------------------------------------
ABQLIB_PATH = r'D:\tools\abaqus-automation\scripts'  # kit's scripts/ dir (holds abqlib); __file__ is undefined in noGUI
CAE_PATH    = r'D:\path\to\model.cae'        # which CAE (mind the Abaqus version!)
MODEL_NAME  = 'Model-1'
REPORT_PATH = r'D:\path\to\_this_script.txt'  # NOT the shell-redirect .log
BACKUP_CAE  = True                            # copy <cae>.<timestamp>.bak before saving

EXAMPLE_RP    = (1000.0, 0.0, 0.0)  # mm, source: <drawing / requirement doc>
EXAMPLE_FORCE = (1000.0, 0.0, 0.0)  # N,  source: <requirement doc / Excel cell>
RP_TOLERANCE  = 10.0                # mm, RP coordinate match tolerance

# ----------------------------------------------------------------------
# Library
# ----------------------------------------------------------------------
sys.path.insert(0, ABQLIB_PATH)
from abqlib import session, rp, loads
from abqlib.util import Report, log

# ----------------------------------------------------------------------
# Step functions - take a model, single responsibility, idempotent
# ----------------------------------------------------------------------
def example_step(model):
    """Replace this docstring; describe what the step does."""
    assembly = model.rootAssembly
    rp_key = rp.ensure_rp(assembly, EXAMPLE_RP, tol=RP_TOLERANCE,
                          set_name='Example_RP_Set')
    loads.ensure_cforce(model, 'Example_Load', assembly.sets['Example_RP_Set'],
                        EXAMPLE_FORCE)
    return {'rp_key': rp_key}

# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------
report = Report(REPORT_PATH)
try:
    mdb = session.open_cae(CAE_PATH)          # fails clearly if open in the GUI
    model = session.get_model(mdb, MODEL_NAME)
    log('=== %s ===' % MODEL_NAME)
    report.data['example_step'] = example_step(model)
    session.save_cae(mdb, CAE_PATH, backup=BACKUP_CAE)
    log('Done.')
except Exception:
    log('FAILED - CAE not saved:')
    log(traceback.format_exc())
finally:
    report.close()
