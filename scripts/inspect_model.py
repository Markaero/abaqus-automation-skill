# -*- coding: utf-8 -*-
"""Abaqus CAE model inspection script (read-only).

Reports steps, parts, assembly instances/sets/surfaces, reference points
(with duplicate detection), constraints, loads (with per-step values from
loadStates), point inertias, non-structural masses, and a mass summary.

Invocation:
    abaqus cae noGUI=inspect_model.py -- <cae_path> [model_name] [report_path]

Outputs (stdout is unreliable under noGUI/PowerShell, so always files):
    <report_path>                 text report   (default: _inspect_<cae>.txt in cwd)
    <report_path minus ext>.json  JSON snapshot (diff two snapshots to verify a change)

Pass '-' as model_name to inspect all models while still giving a report_path.

Notes:
    * Py 2.7 / Py 3 compatible: % formatting, no f-strings.
    * Does NOT save the mdb.
"""

from abaqus import *
from abaqusConstants import *
import sys
import os
import math
import json


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

RP_DUP_TOL = 10.0  # mm; flag reference points closer than this as duplicates
SEP_MAJOR = '#' * 60
SEP_MINOR = '=' * 60
SEP_SUB = '-' * 60

LOAD_VALUE_ATTRS = ('cf1', 'cf2', 'cf3', 'cm1', 'cm2', 'cm3',
                    'magnitude', 'comp1', 'comp2', 'comp3')

_lines = []


def out(msg=''):
    """Collect report lines; flushed to file at the end (and echoed)."""
    _lines.append(msg)
    print(msg)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _print_header(title):
    out(SEP_SUB)
    out('  %s' % title)
    out(SEP_SUB)


def _safe_len(container):
    try:
        return len(container)
    except Exception:
        return 0


def _safe_attr(obj, name, default=None):
    """getattr that also swallows the non-AttributeError failures some Abaqus attributes raise."""
    try:
        return getattr(obj, name, default)
    except Exception:
        return default


def _class_name(obj):
    try:
        return obj.__class__.__name__
    except Exception:
        return '<unknown>'


def _sym(value):
    """Symbolic constant -> its name; other values -> str."""
    if value is None:
        return None
    try:
        return value.name
    except Exception:
        return str(value)


def _as_float(value):
    """Return float(value) or None for None / UNSET / symbolic constants."""
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def _fmt_xyz(x, y, z):
    return '(%9.2f, %9.2f, %9.2f)' % (x, y, z)


def _region_name(region):
    name = _safe_attr(region, 'name', None)
    if name:
        return name
    try:
        # load/constraint regions are often tuples: (set_name, 'Assembly', ...)
        return str(tuple(region)[0])
    except Exception:
        pass
    try:
        return str(region)
    except Exception:
        return '<?>'


# ---------------------------------------------------------------------------
# Section reporters (each fills its slice of the JSON snapshot `snap`)
# ---------------------------------------------------------------------------

def report_steps(model, snap):
    steps = model.steps
    _print_header('Steps (%d)' % _safe_len(steps))
    snap['steps'] = []
    if _safe_len(steps) == 0:
        out('  (none)')
        return
    names = list(steps.keys())
    last_analysis = None
    for name in names:
        if _class_name(steps[name]) != 'InitialStep':
            last_analysis = name
    for name in names:
        cls = _class_name(steps[name])
        marker = '  <-- last analysis step' if name == last_analysis else ''
        out('  %-20s (%s)%s' % (name, cls, marker))
        snap['steps'].append({'name': name, 'type': cls})


def report_parts(model, snap):
    parts = model.parts
    _print_header('Parts (%d)' % _safe_len(parts))
    snap['parts'] = {}
    if _safe_len(parts) == 0:
        out('  (none)')
        return
    for name in parts.keys():
        part = parts[name]
        n_elems = _safe_len(_safe_attr(part, 'elements', ()))
        n_nodes = _safe_len(_safe_attr(part, 'nodes', ()))
        out('  %-30s elems=%-7d nodes=%-7d' % (name, n_elems, n_nodes))
        psnap = {'elements': n_elems, 'nodes': n_nodes, 'sets': {}}
        sets = _safe_attr(part, 'sets', None)
        if sets and _safe_len(sets) > 0:
            for sname in sorted(sets.keys()):
                s = sets[sname]
                se = _safe_len(_safe_attr(s, 'elements', ()))
                sn = _safe_len(_safe_attr(s, 'nodes', ()))
                out('      set: %-30s elems=%-6d nodes=%-6d' % (sname, se, sn))
                psnap['sets'][sname] = {'elements': se, 'nodes': sn}
        snap['parts'][name] = psnap


def report_instances(assembly, snap):
    instances = assembly.instances
    _print_header('Assembly Instances (%d)' % _safe_len(instances))
    snap['instances'] = {}
    if _safe_len(instances) == 0:
        out('  (none)')
        return
    for name in instances.keys():
        inst = instances[name]
        # inst.part can raise on ModelFromInputFile + changeKey models
        part_name = _safe_attr(_safe_attr(inst, 'part', None), 'name', '<?>')
        dep = _safe_attr(inst, 'dependent', None)
        dep_str = 'dependent' if dep == ON else ('independent' if dep == OFF else '?')
        out('  %-30s part=%-25s %s' % (name, part_name, dep_str))
        snap['instances'][name] = {'part': part_name, 'dependent': dep_str}


def report_assembly_sets(assembly, snap):
    sets = assembly.sets
    _print_header('Assembly Sets (%d)' % _safe_len(sets))
    snap['assembly_sets'] = {}
    if _safe_len(sets) == 0:
        out('  (none)')
        return
    for name in sorted(sets.keys()):
        s = sets[name]
        se = _safe_len(_safe_attr(s, 'elements', ()))
        sn = _safe_len(_safe_attr(s, 'nodes', ()))
        rp = _safe_len(_safe_attr(s, 'referencePoints', ()))
        out('  %-35s elems=%-6d nodes=%-6d rp=%-3d' % (name, se, sn, rp))
        snap['assembly_sets'][name] = {'elements': se, 'nodes': sn,
                                       'referencePoints': rp}


def report_assembly_surfaces(assembly, snap):
    surfs = assembly.surfaces
    _print_header('Assembly Surfaces (%d)' % _safe_len(surfs))
    snap['assembly_surfaces'] = {}
    if _safe_len(surfs) == 0:
        out('  (none)')
        return
    for name in sorted(surfs.keys()):
        se = _safe_len(_safe_attr(surfs[name], 'elements', ()))
        out('  %-35s elems=%-6d' % (name, se))
        snap['assembly_surfaces'][name] = {'elements': se}


def report_reference_points(assembly, snap):
    feats = assembly.features
    rp_feats = [f for f in feats.keys() if f.startswith('RP-')]
    _print_header('Reference Points (%d)' % len(rp_feats))
    snap['reference_points'] = []
    snap['rp_duplicates'] = []
    if not rp_feats:
        out('  (none)')
        return

    repo_keys = set()
    try:
        for k in assembly.referencePoints.keys():
            repo_keys.add(int(k))
    except Exception:
        pass

    coords = []  # (name, id, x, y, z)
    for fname in rp_feats:
        feat = feats[fname]
        rp_id = _safe_attr(feat, 'id', None)
        x = _safe_attr(feat, 'xValue', None)
        y = _safe_attr(feat, 'yValue', None)
        z = _safe_attr(feat, 'zValue', None)
        in_repo = rp_id is not None and int(rp_id) in repo_keys
        entry = {'feature': fname, 'id': rp_id, 'in_repo': in_repo}
        if x is None or y is None or z is None:
            out('  %-8s id=%-4s  (no xyz on feature)  [in repo: %s]' % (
                fname, str(rp_id), 'yes' if in_repo else 'no'))
        else:
            out('  %-8s id=%-4s  %s  [in repo: %s]' % (
                fname, str(rp_id), _fmt_xyz(x, y, z), 'yes' if in_repo else 'no'))
            coords.append((fname, rp_id, x, y, z))
            entry['xyz'] = [x, y, z]
        snap['reference_points'].append(entry)

    for i in range(len(coords)):
        for j in range(i + 1, len(coords)):
            n1, _, x1, y1, z1 = coords[i]
            n2, _, x2, y2, z2 = coords[j]
            d = math.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2 + (z1 - z2) ** 2)
            if d < RP_DUP_TOL:
                out('  WARNING: %s and %s within %.2fmm (d=%.3f) - duplicates?' % (
                    n1, n2, RP_DUP_TOL, d))
                snap['rp_duplicates'].append([n1, n2, d])
    if not snap['rp_duplicates']:
        out('  (no duplicate reference points within %.2fmm)' % RP_DUP_TOL)


def report_constraints(model, snap):
    cons = _safe_attr(model, 'constraints', {})
    _print_header('Constraints (%d)' % _safe_len(cons))
    snap['constraints'] = {}
    if _safe_len(cons) == 0:
        out('  (none)')
        return
    for name in cons.keys():
        c = cons[name]
        cls = _class_name(c)
        ctype = _sym(_safe_attr(c, 'couplingType', None))
        suppressed = bool(_safe_attr(c, 'suppressed', False))
        extra = ''
        if ctype:
            extra += '  type=%s' % ctype
        if suppressed:
            extra += '  [SUPPRESSED]'
        out('  %-30s %-15s%s' % (name, cls, extra))
        snap['constraints'][name] = {'type': cls, 'couplingType': ctype,
                                     'suppressed': suppressed}


def _load_values(obj):
    vals = {}
    for attr in LOAD_VALUE_ATTRS:
        v = _as_float(_safe_attr(obj, attr, None))
        if v is not None:
            vals[attr] = v
    return vals


def _fmt_vals(vals):
    return ', '.join(['%s=%.6g' % (k, vals[k]) for k in LOAD_VALUE_ATTRS if k in vals])


def report_loads(model, snap):
    loads = model.loads
    _print_header('Loads (%d)' % _safe_len(loads))
    snap['loads'] = {}
    if _safe_len(loads) == 0:
        out('  (none)')
        return
    step_names = [s for s in model.steps.keys()
                  if _class_name(model.steps[s]) != 'InitialStep']
    for name in loads.keys():
        load = loads[name]
        cls = _class_name(load)
        region_name = _region_name(_safe_attr(load, 'region', None))
        suppressed = bool(_safe_attr(load, 'suppressed', False))
        follower = _sym(_safe_attr(load, 'follower', None))
        out('  %-25s %-20s region=%s%s' % (
            name, cls, region_name, '  [SUPPRESSED]' if suppressed else ''))
        lsnap = {'type': cls, 'region': region_name, 'suppressed': suppressed,
                 'follower': follower, 'steps': {}}
        # Values live on loadStates (loads have no cf1/magnitude members);
        # the load object's own attributes can be None after .inp re-import.
        for sname in step_names:
            try:
                states = model.steps[sname].loadStates
                if name not in states.keys():
                    continue
                state = states[name]
            except Exception:
                continue
            vals = _load_values(state)
            status = _sym(_safe_attr(state, 'status', None))
            out('      step=%-15s status=%-12s %s' % (sname, status or '-', _fmt_vals(vals)))
            lsnap['steps'][sname] = {'status': status, 'values': vals}
        if not lsnap['steps']:
            vals = _load_values(load)
            if vals:
                out('      (load object) %s' % _fmt_vals(vals))
            lsnap['values'] = vals
        if follower:
            out('      follower=%s' % follower)
        snap['loads'][name] = lsnap


def _inertia_owners(model):
    """(label, engineeringFeatures) for the assembly and every part."""
    owners = [('assembly', _safe_attr(model.rootAssembly, 'engineeringFeatures', None))]
    for pname in model.parts.keys():
        owners.append(('part=%s' % pname,
                       _safe_attr(model.parts[pname], 'engineeringFeatures', None)))
    return owners


def report_inertias(model, snap):
    """Point masses, non-structural masses and other inertias.

    All of them live in engineeringFeatures.inertias (on the assembly and on
    each part); there is no separate NSM repository.
    """
    lines = []
    point_total = 0.0
    nsm_total = 0.0
    snap['inertias'] = {}
    for owner, eng in _inertia_owners(model):
        repo = _safe_attr(eng, 'inertias', None) if eng is not None else None
        try:
            names = list(repo.keys())
        except Exception:
            continue
        for name in names:
            it = repo[name]
            cls = _class_name(it)
            region_name = _region_name(_safe_attr(it, 'region', None))
            entry = {'owner': owner, 'type': cls, 'region': region_name,
                     'suppressed': bool(_safe_attr(it, 'suppressed', False))}
            if cls == 'PointMassInertia':
                mass = _as_float(_safe_attr(it, 'mass', None))
                entry['mass_per_point'] = mass
                if mass is not None:
                    point_total += mass
                lines.append('  %-16s %-25s PointMass mass=%s per point  region=%s' % (
                    owner, name, ('%.6g' % mass) if mass is not None else '<aniso/none>',
                    region_name))
            elif cls == 'NonstructuralMass':
                mag = _as_float(_safe_attr(it, 'magnitude', None))
                units = _sym(_safe_attr(it, 'units', None)) or ''
                dist = _sym(_safe_attr(it, 'distribution', None)) or ''
                entry.update({'magnitude': mag, 'units': units, 'distribution': dist})
                if mag is not None and units == 'TOTAL_MASS':
                    nsm_total += mag
                lines.append('  %-16s %-25s NSM mag=%s units=%s dist=%s region=%s' % (
                    owner, name, ('%.6g' % mag) if mag is not None else '<none>',
                    units, dist, region_name))
            else:
                lines.append('  %-16s %-25s %s region=%s' % (owner, name, cls, region_name))
            if entry['suppressed']:
                lines[-1] += '  [SUPPRESSED]'
            snap['inertias']['%s/%s' % (owner, name)] = entry
    _print_header('Inertias: point masses, NSM, other (%d)' % len(lines))
    if not lines:
        out('  (none)')
    for line in lines:
        out(line)
    if lines:
        out('  -- point masses: sum of per-point values (x number of points not applied): %.6g' % point_total)
        out('  -- NSM: sum of TOTAL_MASS entries: %.6g' % nsm_total)
    return point_total, nsm_total


def report_mass_summary(point_inertia_total, nsm_total, snap):
    _print_header('Mass Summary')
    out('  point inertia (sum per-point) : %.6g tonne' % point_inertia_total)
    out('  NSM (TOTAL_MASS only)         : %.6g tonne' % nsm_total)
    out('  Structural mass is not included; read it from the .dat after a run.')
    snap['mass_summary'] = {'point_inertia_per_point_sum': point_inertia_total,
                            'nsm_total_mass': nsm_total}


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def inspect_model(model):
    snap = {}
    out('')
    out(SEP_MAJOR)
    out('# MODEL: %s' % model.name)
    out(SEP_MAJOR)
    report_steps(model, snap)
    report_parts(model, snap)
    assembly = model.rootAssembly
    report_instances(assembly, snap)
    report_assembly_sets(assembly, snap)
    report_assembly_surfaces(assembly, snap)
    report_reference_points(assembly, snap)
    report_constraints(model, snap)
    report_loads(model, snap)
    pi_total, nsm_total = report_inertias(model, snap)
    report_mass_summary(pi_total, nsm_total, snap)
    return snap


def _parse_args():
    """Args after '--' (API trap #2: Abaqus may inject its own flags before it)."""
    if '--' in sys.argv:
        args = sys.argv[sys.argv.index('--') + 1:]
    else:
        args = [a for a in sys.argv[1:]
                if not a.startswith('-') and not a.endswith('.py')]
    return args


def _write_outputs(report_path, snapshot):
    f = open(report_path, 'w')
    f.write('\n'.join(_lines) + '\n')
    f.close()
    json_path = os.path.splitext(report_path)[0] + '.json'
    f = open(json_path, 'w')
    json.dump(snapshot, f, indent=1, sort_keys=True)
    f.close()
    print('Report: %s' % report_path)
    print('JSON  : %s' % json_path)


def main():
    args = _parse_args()
    if not args:
        print('Usage: abaqus cae noGUI=inspect_model.py -- <cae_path> [model_name|-] [report_path]')
        sys.exit(1)
    cae_path = args[0]
    target_model = args[1] if len(args) >= 2 and args[1] != '-' else None
    if len(args) >= 3:
        report_path = args[2]
    else:
        base = os.path.splitext(os.path.basename(cae_path))[0]
        report_path = os.path.join(os.getcwd(), '_inspect_%s.txt' % base)

    snapshot = {'cae': cae_path, 'models': {}}
    out(SEP_MINOR)
    out('  CAE: %s' % cae_path)
    try:
        openMdb(pathName=cae_path)
    except Exception as exc:
        out('  ERROR: failed to open CAE: %s' % exc)
        out('  (Is the .cae open in the CAE GUI? Close it first - API trap #6.)')
        snapshot['error'] = str(exc)
        _write_outputs(report_path, snapshot)
        sys.exit(1)

    model_names = list(mdb.models.keys())
    out('  Models: %s' % model_names)
    out(SEP_MINOR)

    if target_model is not None:
        if target_model not in mdb.models.keys():
            out('  ERROR: model %r not found in CAE' % target_model)
            snapshot['error'] = 'model %r not found' % target_model
            _write_outputs(report_path, snapshot)
            sys.exit(2)
        model_names = [target_model]

    for name in model_names:
        try:
            snapshot['models'][name] = inspect_model(mdb.models[name])
        except Exception as exc:
            out('  ERROR while inspecting %s: %s' % (name, exc))
            snapshot['models'][name] = {'error': str(exc)}

    out('')
    out(SEP_MINOR)
    out('  Inspection complete (mdb NOT saved).')
    out(SEP_MINOR)
    _write_outputs(report_path, snapshot)


main()
