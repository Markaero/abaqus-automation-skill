# -*- coding: utf-8 -*-
"""ODB post-processing (works in `abaqus python` and noGUI): history values, IR summary, field max.

The launcher must match the Abaqus version that wrote the ODB (API trap #10).
"""

G_MMS2 = 9806.65
IR_PREFIXES = ('IRA', 'IRF', 'IRM')


def open_odb(path):
    """openOdb read-only."""
    from odbAccess import openOdb
    return openOdb(path=path, readOnly=True)


def history_last_values(odb_path, step=None, prefixes=None):
    """{step: {region: {var: last_value}}} from history outputs; filter vars by name prefixes."""
    odb = open_odb(odb_path)
    try:
        out = {}
        steps = [step] if step else list(odb.steps.keys())
        for sname in steps:
            s = odb.steps[sname]
            sd = {}
            for rname in s.historyRegions.keys():
                hos = s.historyRegions[rname].historyOutputs
                rd = {}
                for var in hos.keys():
                    if prefixes and not [p for p in prefixes if var.upper().startswith(p)]:
                        continue
                    data = hos[var].data
                    if data:
                        rd[var] = float(data[-1][1])
                if rd:
                    sd[rname] = rd
            out[sname] = sd
        return out
    finally:
        odb.close()


def ir_summary(odb_path, step=None):
    """Inertia-relief results {IRA1..: value, IRA1_g..: value/g} for the last step (or given step)."""
    hist = history_last_values(odb_path, step, IR_PREFIXES)
    sname = step or list(hist.keys())[-1]
    flat = {}
    for rd in hist[sname].values():
        flat.update(rd)
    for k in list(flat.keys()):
        if k.upper().startswith('IRA') and not k.upper().startswith('IRAR'):
            flat[k + '_g'] = flat[k] / G_MMS2
    return flat


def _find_set(odb, set_name, kind):
    """Case-insensitive lookup of an element/node set on the assembly or any instance (ODB set names are often uppercase)."""
    attr = 'elementSets' if kind == 'element' else 'nodeSets'
    ra = odb.rootAssembly
    repos = [getattr(ra, attr)] + [getattr(ra.instances[i], attr) for i in ra.instances.keys()]
    for repo in repos:
        for k in repo.keys():
            if k.upper() == set_name.upper():
                return repo[k]
    raise KeyError('%s set %r not in ODB' % (kind, set_name))


def field_max(odb_path, var, step=None, frame=-1, component=None, invariant=None,
              set_name=None, set_kind='element'):
    """Max |value| of a field output. component=0/1/2 or invariant='mises'/'magnitude'. Returns (value, label)."""
    odb = open_odb(odb_path)
    try:
        sname = step or list(odb.steps.keys())[-1]
        field = odb.steps[sname].frames[frame].fieldOutputs[var]
        if set_name:
            field = field.getSubset(region=_find_set(odb, set_name, set_kind))
        best, label = None, None
        for v in field.values:
            if invariant:
                x = abs(getattr(v, invariant))
            elif component is not None:
                x = abs(v.data[component])
            else:
                x = abs(v.data) if not hasattr(v.data, '__len__') else abs(v.magnitude)
            if best is None or x > best:
                best = x
                label = v.elementLabel if v.elementLabel is not None else v.nodeLabel
        return best, label
    finally:
        odb.close()
