# -*- coding: utf-8 -*-
"""Constraints: couplings (DISTRIBUTING/KINEMATIC), ties, equations, cylindrical csys."""

import regionToolset
from abaqusConstants import (ON, OFF, DISTRIBUTING, KINEMATIC, WHOLE_SURFACE,
                             UNIFORM, ROTATIONAL_STRUCTURAL, CYLINDRICAL)
from caeModules import *   # binds model.Coupling/Tie/Equation in noGUI (API gotcha #10)

from abqlib.util import log, status, has_key


def ensure_coupling(model, name, control_rp_key, surface, kind='DISTRIBUTING',
                    beam_ring=False, dofs=(1, 1, 1, 1, 1, 1), csys=None):
    """RP -> surface/node-region coupling. kind: 'DISTRIBUTING' (RBE3, no added stiffness) or 'KINEMATIC' (RBE2, rigid).

    surface: an assembly Surface/Set or a Region. For a beam node ring pass
    beam_ring=True (DISTRIBUTING + ROTATIONAL_STRUCTURAL to carry moments).
    """
    asm = model.rootAssembly
    existed = has_key(model.constraints, name)
    if existed:
        del model.constraints[name]
    flags = [ON if d else OFF for d in dofs]
    kw = dict(name=name,
              controlPoint=regionToolset.Region(
                  referencePoints=(asm.referencePoints[control_rp_key],)),
              surface=surface, influenceRadius=WHOLE_SURFACE, localCsys=csys,
              u1=flags[0], u2=flags[1], u3=flags[2],
              ur1=flags[3], ur2=flags[4], ur3=flags[5])
    if kind.upper() == 'DISTRIBUTING':
        kw['couplingType'] = DISTRIBUTING
        kw['weightingMethod'] = UNIFORM
        if beam_ring:
            kw['rotationalCouplingType'] = ROTATIONAL_STRUCTURAL
    elif kind.upper() == 'KINEMATIC':
        kw['couplingType'] = KINEMATIC
    else:
        raise ValueError('kind must be DISTRIBUTING or KINEMATIC')
    c = model.Coupling(**kw)
    log('  Coupling %s (%s%s) %s' % (name, kind.upper(),
                                     ', beam ring' if beam_ring else '', status(existed)))
    return c


def node_region(assembly, set_name):
    """Region over the nodes of an assembly set (coupling target for beam rings)."""
    return regionToolset.Region(nodes=assembly.sets[set_name].nodes)


def ensure_tie(model, name, main_surface, secondary_surface, position_tolerance=None,
               adjust=ON, tie_rotations=ON):
    """Tie constraint. Uses main/secondary (2022+) and falls back to master/slave on older Abaqus."""
    existed = has_key(model.constraints, name)
    if existed:
        del model.constraints[name]
    kw = dict(name=name, adjust=adjust, tieRotations=tie_rotations)
    if position_tolerance is not None:
        from abaqusConstants import SPECIFIED
        kw['positionToleranceMethod'] = SPECIFIED
        kw['positionTolerance'] = position_tolerance
    try:
        c = model.Tie(main=main_surface, secondary=secondary_surface, **kw)
    except TypeError:
        c = model.Tie(master=main_surface, slave=secondary_surface, **kw)
    log('  Tie %s %s' % (name, status(existed)))
    return c


def ensure_equation(model, name, terms):
    """*Equation from terms ((coef, set_name, dof[, csys_id]), ...). Sets must hold ONE node each."""
    existed = has_key(model.constraints, name)
    if existed:
        del model.constraints[name]
    c = model.Equation(name=name, terms=tuple([tuple(t) for t in terms]))
    log('  Equation %s %s' % (name, status(existed)))
    return c


def find_cylindrical_csys(assembly, name=None):
    """Datum id of a CYLINDRICAL csys (by feature name if given, else the first found), or None."""
    if name is not None:
        if has_key(assembly.features, name):
            return assembly.features[name].id
        return None
    for k in assembly.datums.keys():
        d = assembly.datums[k]
        if type(d).__name__ == 'DatumCsys' and getattr(d, 'coordSysType', None) == CYLINDRICAL:
            return k
    return None


def ensure_cylindrical_csys(assembly, name, origin, point1, line2):
    """Cylindrical datum csys (R toward point1, T along line2, Z = R x T). Returns its datum id; reuses by name."""
    cid = find_cylindrical_csys(assembly, name)
    if cid is not None:
        log('  Csys %s reused (id=%s)' % (name, cid))
        return cid
    feat = assembly.DatumCsysByThreePoints(name=name, coordSysType=CYLINDRICAL,
                                           origin=tuple(origin), point1=tuple(point1),
                                           line2=tuple(line2))
    log('  Csys %s created (id=%s)' % (name, feat.id))
    return feat.id


def pair_equations(model, prefix, pairs, dofs=(1, 2), csys_id=None):
    """Two-node equations u_a - u_b = 0 per DOF for each (set_a, set_b) pair. Names <prefix>_D<dof>_<i>."""
    names = []
    for i, (a, b) in enumerate(pairs):
        for dof in dofs:
            ta = (1.0, a, dof) if csys_id is None else (1.0, a, dof, csys_id)
            tb = (-1.0, b, dof) if csys_id is None else (-1.0, b, dof, csys_id)
            n = '%s_D%d_%d' % (prefix, dof, i + 1)
            ensure_equation(model, n, (ta, tb))
            names.append(n)
    return names
