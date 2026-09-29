# -*- coding: utf-8 -*-
"""Steps & output requests: static step, field outputs, history outputs."""

from abaqusConstants import ON, OFF

from abqlib.util import log, has_key


def ensure_static_step(model, name, previous='Initial', nlgeom=False, **kw):
    """Create a StaticStep, or update nlgeom/kw on an existing one (keeps loads bound to it)."""
    flag = ON if nlgeom else OFF
    if has_key(model.steps, name):
        model.steps[name].setValues(nlgeom=flag, **kw)
        log('  Step %s updated (nlgeom=%s)' % (name, nlgeom))
    else:
        model.StaticStep(name=name, previous=previous, nlgeom=flag, **kw)
        log('  Step %s created after %s (nlgeom=%s)' % (name, previous, nlgeom))
    return model.steps[name]


def set_field_outputs(model, variables=('S', 'U', 'RF'), request='F-Output-1'):
    """Set the variables of a field output request (default F-Output-1)."""
    model.fieldOutputRequests[request].setValues(variables=tuple(variables))
    log('  Field output %s = %s' % (request, tuple(variables)))


def ensure_history_output(model, name, step, variables, region=None):
    """Create or replace a history output request (e.g. variables=('IRA1','IRF1',...) or energies)."""
    if has_key(model.historyOutputRequests, name):
        del model.historyOutputRequests[name]
    kw = dict(name=name, createStepName=step, variables=tuple(variables))
    if region is not None:
        kw['region'] = region
    model.HistoryOutputRequest(**kw)
    log('  History output %s = %s' % (name, tuple(variables)))
