# -*- coding: utf-8 -*-
"""Masses: point masses at RPs (total auto-split), non-structural mass on part sets."""

from abaqusConstants import TOTAL_MASS, MASS_PROPORTIONAL

from abqlib.util import log, status, has_key
from abqlib.rp import rp_region


def ensure_point_mass(assembly, name, rp_keys, total_mass):
    """PointMassInertia of total_mass (tonne) spread equally over rp_keys - pre-divides per RP (gotcha #9)."""
    if not isinstance(rp_keys, (list, tuple)):
        rp_keys = [rp_keys]
    inertias = assembly.engineeringFeatures.inertias
    existed = has_key(inertias, name)
    if existed:
        del inertias[name]
    per = float(total_mass) / len(rp_keys)
    obj = assembly.engineeringFeatures.PointMassInertia(
        name=name, region=rp_region(assembly, rp_keys), mass=per,
        alpha=0.0, composite=0.0)
    log('  PointMass %s total=%g t over %d RP(s) -> %g each %s'
        % (name, total_mass, len(rp_keys), per, status(existed)))
    return obj


def ensure_nsm(part, name, set_name, total_mass, distribution=MASS_PROPORTIONAL):
    """Non-structural TOTAL_MASS (tonne) on a part-level set, distributed MASS_PROPORTIONAL by default."""
    nsms = part.engineeringFeatures.nonstructuralMasses
    existed = has_key(nsms, name)
    if existed:
        del nsms[name]
    obj = part.engineeringFeatures.NonstructuralMass(
        name=name, region=part.sets[set_name], units=TOTAL_MASS,
        magnitude=float(total_mass), distribution=distribution)
    log('  NSM %s %g t on %s %s' % (name, total_mass, set_name, status(existed)))
    return obj
