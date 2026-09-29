# -*- coding: utf-8 -*-
"""Masses: point masses at RPs (total auto-split), non-structural mass on sets.

Both kinds live in the same repository, engineeringFeatures.inertias
(there is no separate NSM repository), so names must be unique across them.
"""

from abaqusConstants import TOTAL_MASS, MASS_PROPORTIONAL

from abqlib.util import log, status, has_key
from abqlib.rp import rp_region


def ensure_point_mass(assembly, name, rp_keys, total_mass):
    """PointMassInertia of total_mass (tonne) spread equally over rp_keys - the API applies mass to EACH point, so this pre-divides."""
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


def ensure_nsm(owner, name, set_name, total_mass, distribution=MASS_PROPORTIONAL):
    """Non-structural TOTAL_MASS (tonne) on a set of a part or the assembly (owner), MASS_PROPORTIONAL by default."""
    inertias = owner.engineeringFeatures.inertias
    existed = has_key(inertias, name)
    if existed:
        del inertias[name]
    obj = owner.engineeringFeatures.NonstructuralMass(
        name=name, region=owner.sets[set_name], units=TOTAL_MASS,
        magnitude=float(total_mass), distribution=distribution)
    log('  NSM %s %g t on %s %s' % (name, total_mass, set_name, status(existed)))
    return obj
