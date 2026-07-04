# -*- coding: mbcs -*-
"""Abaqus CAE model inspection script.

Reusable read-only inspector for an Abaqus .cae database. Prints a structured
report covering steps, parts, assembly instances/sets/surfaces, reference
points (with orphan-feature and duplicate detection), constraints, loads,
point inertias, non-structural masses, and an overall mass summary.

Invocation:
    abaqus cae noGUI=inspect_model.py -- <cae_path> [model_name]

Defaults:
    cae_path   -> (required, pass as first argument after --)
    model_name -> (none) iterate all models in the database

Notes:
    * Designed for Abaqus Python 2.7. No f-strings; uses % formatting.
    * Does NOT save the mdb (read-only inspection).
"""

from abaqus import *
from abaqusConstants import *
import sys
import math


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_CAE = ''  # pass as: abaqus cae noGUI=inspect_model.py -- <your.cae>
RP_DUP_TOL = 10.0  # mm; flag reference points closer than this as duplicates
SEP_MAJOR = '#' * 60
SEP_MINOR = '=' * 60
SEP_SUB = '-' * 60


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _print_header(title):
    print(SEP_SUB)
    print('  %s' % title)
    print(SEP_SUB)


def _safe_len(container):
    try:
        return len(container)
    except Exception:
        return 0


def _class_name(obj):
    try:
        return obj.__class__.__name__
    except Exception:
        return '<unknown>'


def _fmt_xyz(x, y, z):
    return '(%9.2f, %9.2f, %9.2f)' % (x, y, z)


# ---------------------------------------------------------------------------
# Section reporters
# ---------------------------------------------------------------------------

def report_steps(model):
    steps = model.steps
    _print_header('Steps (%d)' % _safe_len(steps))
    if _safe_len(steps) == 0:
        print('  (none)')
        return
    last_analysis = None
    for name in steps.keys():
        step = steps[name]
        cls = _class_name(step)
        if cls != 'InitialStep':
            last_analysis = name
    for name in steps.keys():
        step = steps[name]
        cls = _class_name(step)
        marker = '  <-- last analysis step' if name == last_analysis else ''
        print('  %-20s (%s)%s' % (name, cls, marker))


def report_parts(model):
    parts = model.parts
    _print_header('Parts (%d)' % _safe_len(parts))
    if _safe_len(parts) == 0:
        print('  (none)')
        return
    for name in parts.keys():
        part = parts[name]
        n_elems = _safe_len(getattr(part, 'elements', ()))
        n_nodes = _safe_len(getattr(part, 'nodes', ()))
        print('  %-30s elems=%-7d nodes=%-7d' % (name, n_elems, n_nodes))
        sets = getattr(part, 'sets', None)
        if sets and _safe_len(sets) > 0:
            for sname in sorted(sets.keys()):
                s = sets[sname]
                se = _safe_len(getattr(s, 'elements', ()))
                sn = _safe_len(getattr(s, 'nodes', ()))
                print('      set: %-30s elems=%-6d nodes=%-6d' % (sname, se, sn))


def report_instances(assembly):
    instances = assembly.instances
    _print_header('Assembly Instances (%d)' % _safe_len(instances))
    if _safe_len(instances) == 0:
        print('  (none)')
        return
    for name in instances.keys():
        inst = instances[name]
        part_name = getattr(getattr(inst, 'part', None), 'name', '<?>')
        dep = getattr(inst, 'dependent', None)
        dep_str = 'dependent' if dep == ON else ('independent' if dep == OFF else '?')
        print('  %-30s part=%-25s %s' % (name, part_name, dep_str))


def report_assembly_sets(assembly):
    sets = assembly.sets
    _print_header('Assembly Sets (%d)' % _safe_len(sets))
    if _safe_len(sets) == 0:
        print('  (none)')
        return
    for name in sorted(sets.keys()):
        s = sets[name]
        se = _safe_len(getattr(s, 'elements', ()))
        sn = _safe_len(getattr(s, 'nodes', ()))
        rp = _safe_len(getattr(s, 'referencePoints', ()))
        print('  %-35s elems=%-6d nodes=%-6d rp=%-3d' % (name, se, sn, rp))


def report_assembly_surfaces(assembly):
    surfs = assembly.surfaces
    _print_header('Assembly Surfaces (%d)' % _safe_len(surfs))
    if _safe_len(surfs) == 0:
        print('  (none)')
        return
    for name in sorted(surfs.keys()):
        s = surfs[name]
        se = _safe_len(getattr(s, 'elements', ()))
        print('  %-35s elems=%-6d' % (name, se))


def report_reference_points(assembly):
    feats = assembly.features
    rp_feats = []
    for fname in feats.keys():
        if fname.startswith('RP-'):
            rp_feats.append(fname)
    _print_header('Reference Points (%d)' % len(rp_feats))
    if not rp_feats:
        print('  (none)')
        return

    rp_repo = getattr(assembly, 'referencePoints', {})
    repo_keys = set()
    try:
        for k in rp_repo.keys():
            repo_keys.add(int(k))
    except Exception:
        pass

    coords = []  # list of (name, id, x, y, z)
    for fname in rp_feats:
        feat = feats[fname]
        rp_id = getattr(feat, 'id', None)
        x = getattr(feat, 'xValue', None)
        y = getattr(feat, 'yValue', None)
        z = getattr(feat, 'zValue', None)
        in_repo = 'yes' if (rp_id is not None and int(rp_id) in repo_keys) else 'no'
        if x is None or y is None or z is None:
            print('  %-8s id=%-4s  (no xyz on feature)  [in repo: %s]' % (
                fname, str(rp_id), in_repo))
        else:
            print('  %-8s id=%-4s  %s  [in repo: %s]' % (
                fname, str(rp_id), _fmt_xyz(x, y, z), in_repo))
            coords.append((fname, rp_id, x, y, z))

    # Duplicate detection
    flagged = False
    for i in range(len(coords)):
        for j in range(i + 1, len(coords)):
            n1, _, x1, y1, z1 = coords[i]
            n2, _, x2, y2, z2 = coords[j]
            d = math.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2 + (z1 - z2) ** 2)
            if d < RP_DUP_TOL:
                print('  WARNING: %s and %s within %.2fmm (d=%.3f) - duplicates?' % (
                    n1, n2, RP_DUP_TOL, d))
                flagged = True
    if not flagged:
        print('  (no duplicate reference points within %.2fmm)' % RP_DUP_TOL)


def report_constraints(model):
    cons = getattr(model, 'constraints', {})
    _print_header('Constraints (%d)' % _safe_len(cons))
    if _safe_len(cons) == 0:
        print('  (none)')
        return
    for name in cons.keys():
        c = cons[name]
        cls = _class_name(c)
        ctype = getattr(c, 'couplingType', None)
        ctype_str = ''
        if ctype is not None:
            try:
                ctype_str = '  type=%s' % ctype.name
            except Exception:
                ctype_str = '  type=%s' % str(ctype)
        print('  %-30s %-15s%s' % (name, cls, ctype_str))


def _fmt_load_magnitudes(load):
    cls = _class_name(load)
    parts = []
    if cls == 'ConcentratedForce':
        cf1 = getattr(load, 'cf1', None)
        cf2 = getattr(load, 'cf2', None)
        cf3 = getattr(load, 'cf3', None)
        parts.append('cf=(%s, %s, %s)' % (
            ('%.3f' % cf1) if cf1 is not None else '-',
            ('%.3f' % cf2) if cf2 is not None else '-',
            ('%.3f' % cf3) if cf3 is not None else '-'))
    elif cls == 'Moment':
        cm1 = getattr(load, 'cm1', None)
        cm2 = getattr(load, 'cm2', None)
        cm3 = getattr(load, 'cm3', None)
        parts.append('cm=(%s, %s, %s)' % (
            ('%.3f' % cm1) if cm1 is not None else '-',
            ('%.3f' % cm2) if cm2 is not None else '-',
            ('%.3f' % cm3) if cm3 is not None else '-'))
    elif cls == 'Pressure':
        mag = getattr(load, 'magnitude', None)
        parts.append('mag=%s' % (('%.4f' % mag) if mag is not None else '-'))
    elif cls == 'Gravity':
        c1 = getattr(load, 'comp1', None)
        c2 = getattr(load, 'comp2', None)
        c3 = getattr(load, 'comp3', None)
        parts.append('g=(%s, %s, %s)' % (
            ('%.3f' % c1) if c1 is not None else '-',
            ('%.3f' % c2) if c2 is not None else '-',
            ('%.3f' % c3) if c3 is not None else '-'))
    else:
        mag = getattr(load, 'magnitude', None)
        if mag is not None:
            parts.append('mag=%.4f' % mag)
    follower = getattr(load, 'follower', None)
    if follower is not None:
        try:
            parts.append('follower=%s' % follower.name)
        except Exception:
            parts.append('follower=%s' % str(follower))
    return '   '.join(parts)


def report_loads(model):
    loads = model.loads
    _print_header('Loads (%d)' % _safe_len(loads))
    if _safe_len(loads) == 0:
        print('  (none)')
        return
    for name in loads.keys():
        load = loads[name]
        cls = _class_name(load)
        step = getattr(load, 'createStepName', '<?>')
        region = getattr(load, 'region', None)
        region_name = getattr(region, 'name', None)
        if region_name is None:
            try:
                region_name = str(region)
            except Exception:
                region_name = '<?>'
        print('  %-25s %-20s step=%-15s region=%s' % (
            name, cls, step, region_name))
        details = _fmt_load_magnitudes(load)
        if details:
            print('      %s' % details)


def report_point_inertias(assembly):
    eng = getattr(assembly, 'engineeringFeatures', None)
    inertias = getattr(eng, 'inertias', None) if eng is not None else None
    n = _safe_len(inertias) if inertias is not None else 0
    _print_header('Point Inertias (%d)' % n)
    if n == 0:
        print('  (none)')
        return 0.0
    total = 0.0
    for name in inertias.keys():
        it = inertias[name]
        mass = getattr(it, 'mass', None)
        region = getattr(it, 'region', None)
        region_name = getattr(region, 'name', None)
        if region_name is None:
            try:
                region_name = str(region)
            except Exception:
                region_name = '<?>'
        if mass is None:
            print('  %-30s mass=<none>     region=%s' % (name, region_name))
        else:
            try:
                total += float(mass)
            except Exception:
                pass
            print('  %-30s mass=%-12.6g region=%s' % (name, mass, region_name))
    print('  -- point inertia total mass: %.6g' % total)
    return total


def report_nsm(model):
    parts = model.parts
    total = 0.0
    nsm_lines = []
    count = 0
    for pname in parts.keys():
        part = parts[pname]
        eng = getattr(part, 'engineeringFeatures', None)
        if eng is None:
            continue
        nsm = getattr(eng, 'nonstructuralMasses', None)
        if nsm is None:
            nsm = getattr(eng, 'nonstructuralMass', None)
        if nsm is None:
            continue
        try:
            keys = nsm.keys()
        except Exception:
            continue
        for nname in keys:
            entry = nsm[nname]
            mag = getattr(entry, 'magnitude', None)
            units = getattr(entry, 'units', None)
            units_str = ''
            if units is not None:
                try:
                    units_str = units.name
                except Exception:
                    units_str = str(units)
            dist = getattr(entry, 'distribution', None)
            dist_str = ''
            if dist is not None:
                try:
                    dist_str = dist.name
                except Exception:
                    dist_str = str(dist)
            count += 1
            if mag is not None:
                try:
                    total += float(mag)
                except Exception:
                    pass
            nsm_lines.append(
                '  part=%-20s name=%-25s mag=%-12s units=%-15s dist=%s' % (
                    pname, nname,
                    ('%.6g' % mag) if mag is not None else '<none>',
                    units_str, dist_str))
    _print_header('Non-Structural Masses (%d)' % count)
    if count == 0:
        print('  (none)')
        return 0.0
    for line in nsm_lines:
        print(line)
    print('  -- NSM total magnitude (raw sum, ignore units mix): %.6g' % total)
    return total


def report_mass_summary(point_inertia_total, nsm_total):
    _print_header('Mass Summary')
    print('  point inertia mass : %.6g (tonne, assumed)' % point_inertia_total)
    print('  NSM mass (raw sum) : %.6g (units may be MASS or MASS_PER_*)' % nsm_total)
    print('  total known mass   : %.6g' % (point_inertia_total + nsm_total))


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def inspect_model(model):
    print('')
    print(SEP_MAJOR)
    print('# MODEL: %s' % model.name)
    print(SEP_MAJOR)
    report_steps(model)
    report_parts(model)
    assembly = model.rootAssembly
    report_instances(assembly)
    report_assembly_sets(assembly)
    report_assembly_surfaces(assembly)
    report_reference_points(assembly)
    report_constraints(model)
    report_loads(model)
    pi_total = report_point_inertias(assembly)
    nsm_total = report_nsm(model)
    report_mass_summary(pi_total, nsm_total)


def main():
    if '--' in sys.argv:
        args = sys.argv[sys.argv.index('--') + 1:]
    else:
        args = sys.argv[2:] if len(sys.argv) > 2 else []
    if len(args) >= 3:
        sys.stdout = open(args[2], 'w')
    cae_path = args[0] if len(args) >= 1 else DEFAULT_CAE
    target_model = args[1] if len(args) >= 2 else None

    print(SEP_MINOR)
    print('  CAE: %s' % cae_path)
    try:
        openMdb(pathName=cae_path)
    except Exception as exc:
        print('  ERROR: failed to open CAE: %s' % exc)
        sys.exit(1)

    model_names = list(mdb.models.keys())
    print('  Models: %s' % model_names)
    print(SEP_MINOR)

    if target_model is not None:
        if target_model not in mdb.models:
            print('  ERROR: model %r not found in CAE' % target_model)
            sys.exit(2)
        inspect_model(mdb.models[target_model])
    else:
        for name in model_names:
            inspect_model(mdb.models[name])

    print('')
    print(SEP_MINOR)
    print('  Inspection complete (mdb NOT saved).')
    print(SEP_MINOR)


if __name__ == '__main__':
    main()
