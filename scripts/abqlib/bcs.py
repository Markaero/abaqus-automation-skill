# -*- coding: utf-8 -*-
"""Boundary conditions: displacement BC, encastre."""

from abaqusConstants import UNSET

from abqlib.util import log, status, has_key


def ensure_displacement_bc(model, name, region, u=(0, 0, 0, 0, 0, 0), step='Initial'):
    """DisplacementBC. u = 6 values (u1,u2,u3,ur1,ur2,ur3); None leaves the DOF free, numbers prescribe it."""
    existed = has_key(model.boundaryConditions, name)
    if existed:
        del model.boundaryConditions[name]
    keys = ('u1', 'u2', 'u3', 'ur1', 'ur2', 'ur3')
    kw = dict(name=name, createStepName=step, region=region)
    for k, v in zip(keys, u):
        kw[k] = UNSET if v is None else float(v)
    bc = model.DisplacementBC(**kw)
    log('  DisplacementBC %s u=%s step=%s %s' % (name, tuple(u), step, status(existed)))
    return bc


def ensure_encastre(model, name, region, step='Initial'):
    """Fully fixed BC (all 6 DOFs) on a region."""
    existed = has_key(model.boundaryConditions, name)
    if existed:
        del model.boundaryConditions[name]
    bc = model.EncastreBC(name=name, createStepName=step, region=region)
    log('  EncastreBC %s step=%s %s' % (name, step, status(existed)))
    return bc
