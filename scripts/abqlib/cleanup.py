# -*- coding: utf-8 -*-
"""Cleanup: delete features in the safe order (loads -> constraints -> masses -> sets/surfaces -> RPs)."""

from abqlib.util import log, has_key
from abqlib.rp import delete_rps_near


def delete_in_order(model, loads=(), constraints=(), inertias=(), sets=(),
                    surfaces=(), rp_points=(), rp_tol=10.0):
    """Delete named objects in the order Abaqus requires (gotcha #8); missing names are skipped. Returns what was deleted."""
    asm = model.rootAssembly
    done = {'loads': [], 'constraints': [], 'inertias': [], 'sets': [],
            'surfaces': [], 'rps': []}
    for n in loads:
        if has_key(model.loads, n):
            del model.loads[n]
            done['loads'].append(n)
    for n in constraints:
        if has_key(model.constraints, n):
            del model.constraints[n]
            done['constraints'].append(n)
    inert = asm.engineeringFeatures.inertias
    for n in inertias:
        if has_key(inert, n):
            del inert[n]
            done['inertias'].append(n)
    for n in sets:
        if has_key(asm.sets, n):
            del asm.sets[n]
            done['sets'].append(n)
    for n in surfaces:
        if has_key(asm.surfaces, n):
            del asm.surfaces[n]
            done['surfaces'].append(n)
    if rp_points:
        done['rps'] = delete_rps_near(asm, rp_points, rp_tol)
    log('  Deleted %s' % dict([(k, v) for k, v in done.items() if v]))
    return done


def delete_by_prefix(model, prefix, loads=True, constraints=True, sets=True, surfaces=True):
    """Delete loads/constraints/sets/surfaces whose name starts with prefix, in safe order."""
    asm = model.rootAssembly

    def pick(repo, on):
        return [n for n in repo.keys() if n.startswith(prefix)] if on else []
    return delete_in_order(model,
                           loads=pick(model.loads, loads),
                           constraints=pick(model.constraints, constraints),
                           sets=pick(asm.sets, sets),
                           surfaces=pick(asm.surfaces, surfaces))
