# -*- coding: utf-8 -*-
"""Loads: concentrated force, moment, pressure, gravity, inertia relief, per-step values, suppress."""

from abaqusConstants import ON, OFF, UNIFORM, FIELD

from abqlib.util import log, status, has_key, get_last_step


def _replace(model, name):
    existed = has_key(model.loads, name)
    if existed:
        del model.loads[name]
    return existed


def ensure_cforce(model, name, region, cf, step=None, follower=False, csys=None):
    """Concentrated force cf=(fx, fy, fz) in N on a set/region. step defaults to the last step.

    follower=True needs an NLGEOM step. None components are left unset.
    """
    step = step or get_last_step(model)
    vals = [c for c in cf if c is not None]
    if not vals or all([v == 0.0 for v in vals]):
        raise ValueError('ConcentratedForce %s: all components are zero' % name)
    existed = _replace(model, name)
    kw = dict(name=name, createStepName=step, region=region,
              distributionType=UNIFORM, follower=ON if follower else OFF, localCsys=csys)
    for i, c in enumerate(cf):
        if c is not None:
            kw['cf%d' % (i + 1)] = float(c)
    ld = model.ConcentratedForce(**kw)
    log('  CForce %s cf=%s step=%s %s' % (name, tuple(cf), step, status(existed)))
    return ld


def ensure_moment(model, name, region, cm, step=None, follower=False, csys=None):
    """Moment cm=(mx, my, mz) in N*mm (convert N*m x1000) on a set/region."""
    step = step or get_last_step(model)
    vals = [c for c in cm if c is not None]
    if not vals or all([v == 0.0 for v in vals]):
        raise ValueError('Moment %s: all components are zero' % name)
    existed = _replace(model, name)
    kw = dict(name=name, createStepName=step, region=region,
              distributionType=UNIFORM, follower=ON if follower else OFF, localCsys=csys)
    for i, c in enumerate(cm):
        if c is not None:
            kw['cm%d' % (i + 1)] = float(c)
    ld = model.Moment(**kw)
    log('  Moment %s cm=%s step=%s %s' % (name, tuple(cm), step, status(existed)))
    return ld


def ensure_pressure(model, name, surface, magnitude, step=None, field=None):
    """Pressure in MPa on a surface. POSITIVE magnitude pushes AGAINST the bound side's normal (API trap #21).

    field: name of a MappedField/analytical field -> distributionType=FIELD and
    magnitude acts as a (sign-flippable) scale.
    """
    step = step or get_last_step(model)
    existed = _replace(model, name)
    kw = dict(name=name, createStepName=step, region=surface, magnitude=float(magnitude))
    if field:
        kw['distributionType'] = FIELD
        kw['field'] = field
    else:
        kw['distributionType'] = UNIFORM
    ld = model.Pressure(**kw)
    log('  Pressure %s mag=%g%s step=%s %s' % (name, magnitude,
                                               ' field=%s' % field if field else '', step, status(existed)))
    return ld


def ensure_gravity(model, name, accel, step=None, region=None):
    """Gravity body load accel=(ax, ay, az) in mm/s^2 (1 g = 9806.65). region=None -> whole model."""
    step = step or get_last_step(model)
    existed = _replace(model, name)
    kw = dict(name=name, createStepName=step, distributionType=UNIFORM,
              comp1=float(accel[0]), comp2=float(accel[1]), comp3=float(accel[2]))
    if region is not None:
        kw['region'] = region
    ld = model.Gravity(**kw)
    log('  Gravity %s a=%s step=%s %s' % (name, tuple(accel), step, status(existed)))
    return ld


def ensure_inertia_relief(model, name='InertiaRelief', step=None, dofs=(1, 1, 1, 1, 1, 1)):
    """Inertia relief on the chosen free-body DOFs; solver reports IRA/IRF/IRM history outputs."""
    step = step or get_last_step(model)
    existed = _replace(model, name)
    f = [ON if d else OFF for d in dofs]
    ld = model.InertiaRelief(name=name, createStepName=step,
                             u1=f[0], u2=f[1], u3=f[2], ur1=f[3], ur2=f[4], ur3=f[5])
    log('  InertiaRelief %s step=%s %s' % (name, step, status(existed)))
    return ld


_VALUE_ATTRS = ('cf1', 'cf2', 'cf3', 'cm1', 'cm2', 'cm3', 'magnitude', 'comp1', 'comp2', 'comp3')


def load_values(model, name, step=None):
    """Numeric values of a load in a step, read from loadStates (loads have no cf1/magnitude members)."""
    step = step or get_last_step(model)
    state = model.steps[step].loadStates[name]
    out = {}
    for a in _VALUE_ATTRS:
        try:
            v = float(getattr(state, a))
        except Exception:
            continue
        out[a] = v
    return out


def set_load_values(model, name, step=None, **values):
    """Change magnitudes of an existing load in a step, e.g. set_load_values(m, 'Thrust', cf3=1e4)."""
    step = step or get_last_step(model)
    ld = model.loads[name]
    created_in = None
    try:
        created_in = ld.createStepName
    except Exception:
        pass
    if created_in == step:
        ld.setValues(**values)
    elif created_in is not None:
        ld.setValuesInStep(stepName=step, **values)
    else:   # createStepName is not a member of most loads: try the step, fall back
        try:
            ld.setValuesInStep(stepName=step, **values)
        except Exception:
            ld.setValues(**values)
    log('  Load %s in %s set %s' % (name, step, values))


def suppress_loads(model, names):
    """Suppress loads by name (in memory). Don't save afterwards if the change is diagnostic only."""
    for n in names:
        model.loads[n].suppress()
    log('  Suppressed loads %s' % list(names))


def resume_loads(model, names):
    """Resume loads previously suppressed."""
    for n in names:
        model.loads[n].resume()
    log('  Resumed loads %s' % list(names))


def suppress_all_but(model, keep):
    """Suppress every active load except those in keep (per-load IR isolation). Returns the suppressed names."""
    names = [n for n in model.loads.keys()
             if n not in keep and not getattr(model.loads[n], 'suppressed', False)]
    suppress_loads(model, names)
    return names
