# -*- coding: utf-8 -*-
"""Template for an Abaqus noGUI automation script.

Copy this file, rename it, edit ONLY the "User inputs" block for reuse.
Conventions:
- utf-8 encoding header (works on Abaqus 2024+; avoid mbcs for ODB scripts)
- standard imports (incl. caeModules for Equation/Coupling/Tie)
- every tunable value lives in the "User inputs" block - no config.py
- idempotent modify-or-create pattern
- write results to a log file; stdout is unreliable under noGUI/PowerShell
- mdb.save() at end (omit for inspection-only scripts)

Run:  abaqus cae noGUI=this_script.py > _this_script.log 2>&1
      (use the launcher matching the CAE version, e.g. abq2024)
"""

from abaqus import *
from abaqusConstants import *
from caeModules import *           # required for model.Equation/Coupling/Tie
import regionToolset
import math

# ----------------------------------------------------------------------
# User inputs, unit = mm, N, tonne  (edit this block only)
# ----------------------------------------------------------------------
CAE_PATH   = r'D:\path\to\model.cae'      # which CAE (mind the Abaqus version!)
MODEL_NAME = 'Model-1'
LOG_PATH   = r'D:\path\to\_this_script.log'

EXAMPLE_FORCE = 1000.0     # N, source: <requirement doc / Excel cell / drawing>
RP_TOLERANCE  = 10.0       # mm, RP coordinate match tolerance

# ----------------------------------------------------------------------
# Logging (write to file; do not rely on stdout)
# ----------------------------------------------------------------------
_fout = open(LOG_PATH, 'w')

def log(msg):
    _fout.write(msg + '\n')
    _fout.flush()
    print(msg)

# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def get_last_step(model):
    """Return the last step name ('Initial' is always first, so [-1] is the last analysis step)."""
    return list(model.steps.keys())[-1]


def ensure_assembly_set(assembly, name, **entities):
    """Create or replace an assembly set. Pass the same kwargs as Set()."""
    if name in assembly.sets.keys():
        del assembly.sets[name]
    return assembly.Set(name=name, **entities)


def find_existing_rp(assembly, x, y, z, tolerance=10.0):
    """Return the referencePoints key of an RP feature within tolerance,
    else None. RP ids renumber after model copy - always look up by coords."""
    for feat_name in assembly.features.keys():
        feat = assembly.features[feat_name]
        if hasattr(feat, 'xValue') and feat.xValue is not None:
            dx = feat.xValue - x
            dy = feat.yValue - y
            dz = feat.zValue - z
            if (dx * dx + dy * dy + dz * dz) ** 0.5 <= tolerance:
                return feat.id
    return None

# ----------------------------------------------------------------------
# Step functions - each takes a model, single responsibility, idempotent
# (pipeline style: build -> partition -> assign -> mesh, one function each)
# ----------------------------------------------------------------------
def example_step(model):
    """Replace this docstring; describe what the step does."""
    assembly = model.rootAssembly
    step_name = get_last_step(model)

    target = (1000.0, 0.0, 0.0)
    rp_id = find_existing_rp(assembly, target[0], target[1], target[2],
                             tolerance=RP_TOLERANCE)
    if rp_id is not None:
        log('  Reusing RP at %s' % str(target))
    else:
        feat = assembly.ReferencePoint(point=target)
        rp_id = feat.id
        log('  Created RP at %s (id=%d)' % (str(target), rp_id))

    ensure_assembly_set(
        assembly, 'Example_RP_Set',
        referencePoints=(assembly.referencePoints[rp_id],),  # trailing comma!
    )

    # Idempotent load: delete then create
    if 'Example_Load' in model.loads.keys():
        del model.loads['Example_Load']
    model.ConcentratedForce(
        name='Example_Load',
        createStepName=step_name,
        region=assembly.sets['Example_RP_Set'],
        cf1=EXAMPLE_FORCE, cf2=0.0, cf3=0.0,
        distributionType=UNIFORM,
        localCsys=None,
    )
    log('  Applied Example_Load (cf1=%.1f N) in step %s'
        % (EXAMPLE_FORCE, step_name))

# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------
mdb = openMdb(pathName=CAE_PATH)

if MODEL_NAME not in mdb.models.keys():
    log('ERROR: model %s not in %s' % (MODEL_NAME, CAE_PATH))
else:
    log('=== %s ===' % MODEL_NAME)
    example_step(mdb.models[MODEL_NAME])
    mdb.save()
    log('Saved %s' % CAE_PATH)

log('Done.')
_fout.close()
