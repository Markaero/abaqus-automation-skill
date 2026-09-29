# -*- coding: utf-8 -*-
"""Sets & surfaces: persistent assembly sets, part->assembly promotion, surfaces, node picking."""

from abqlib.util import log, status, has_key, dist


def ensure_set(assembly, name, **entities):
    """Create or replace an assembly Set; kwargs as Set() (nodes=, elements=, referencePoints=, faces=...)."""
    existed = has_key(assembly.sets, name)
    if existed:
        del assembly.sets[name]
    s = assembly.Set(name=name, **entities)
    log('  Set %s %s' % (name, status(existed)))
    return s


def promote_part_set(model, part_name, set_name, instance_name,
                     node_suffix='_Node', elements=True, nodes=True):
    """Copy a part-level set to the assembly by labels: elements keep the name, nodes get node_suffix.

    Uses SetFromElementLabels/SetFromNodeLabels, which only need the
    instance *name*, so it also works on imported models with a broken
    inst.part accessor (API trap #13).
    """
    asm = model.rootAssembly
    pset = model.parts[part_name].sets[set_name]
    made = []
    if elements and len(pset.elements) > 0:
        labels = tuple([e.label for e in pset.elements])
        if has_key(asm.sets, set_name):
            del asm.sets[set_name]
        asm.SetFromElementLabels(name=set_name, elementLabels=((instance_name, labels),))
        made.append(set_name)
    if nodes and len(pset.nodes) > 0:
        nname = set_name + node_suffix
        labels = tuple([n.label for n in pset.nodes])
        if has_key(asm.sets, nname):
            del asm.sets[nname]
        asm.SetFromNodeLabels(name=nname, nodeLabels=((instance_name, labels),))
        made.append(nname)
    log('  Promoted %s.%s -> %s' % (part_name, set_name, made))
    return made


def ensure_surface(assembly, name, elements, side=1):
    """Create or replace an element-based surface. side=1 -> SPOS (side1Elements), 2 -> SNEG (API trap #21)."""
    existed = has_key(assembly.surfaces, name)
    if existed:
        del assembly.surfaces[name]
    if side == 1:
        s = assembly.Surface(name=name, side1Elements=elements)
    elif side == 2:
        s = assembly.Surface(name=name, side2Elements=elements)
    else:
        raise ValueError('side must be 1 or 2')
    log('  Surface %s (side%d) %s' % (name, side, status(existed)))
    return s


def surface_from_set(assembly, name, set_name, side=1):
    """ensure_surface over the elements of an existing assembly set."""
    return ensure_surface(assembly, name, assembly.sets[set_name].elements, side)


def nearest_node(instance, xyz):
    """(node, distance) of the instance node closest to xyz (linear scan)."""
    best, best_d = None, None
    for n in instance.nodes:
        d = dist(n.coordinates, xyz)
        if best_d is None or d < best_d:
            best, best_d = n, d
    return best, best_d


def node_set_by_coords(assembly, instance_name, name, points, tol=1.0):
    """Assembly node set of the nodes nearest to each point; raises if any is farther than tol.

    Use to transfer node sets between models - labels don't survive
    re-import, coordinates do.
    """
    inst = assembly.instances[instance_name]
    labels = []
    worst = 0.0
    for p in points:
        n, d = nearest_node(inst, p)
        if n is None or d > tol:
            raise ValueError('no node within %.3g of %s (nearest %.3g)' % (tol, tuple(p), d or -1))
        labels.append(n.label)
        worst = max(worst, d)
    if has_key(assembly.sets, name):
        del assembly.sets[name]
    s = assembly.SetFromNodeLabels(name=name, nodeLabels=((instance_name, tuple(labels)),))
    log('  Node set %s: %d nodes, worst match %.4g' % (name, len(labels), worst))
    return s


def long_set_names(assembly, limit=80):
    """Assembly/instance set names whose qualified .inp name exceeds limit chars (solver fails at 80)."""
    bad = [n for n in assembly.sets.keys() if len('ASSEMBLY.%s' % n) > limit]
    for iname in assembly.instances.keys():
        try:
            for n in assembly.instances[iname].sets.keys():
                if len('%s.%s' % (iname, n)) > limit:
                    bad.append('%s.%s' % (iname, n))
        except Exception:
            pass
    return bad
