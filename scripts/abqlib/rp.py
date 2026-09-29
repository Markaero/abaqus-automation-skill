# -*- coding: utf-8 -*-
"""Reference points: find by coordinate, create-if-missing, regions, delete."""

import regionToolset

from abqlib.util import log, dist


def _rp_features(assembly):
    """Yield (feature_name, id, xyz) for features that are live RPs."""
    rp_keys = set(assembly.referencePoints.keys())
    for fname in assembly.features.keys():
        feat = assembly.features[fname]
        fid = getattr(feat, 'id', None)
        if fid not in rp_keys or getattr(feat, 'xValue', None) is None:
            continue
        yield fname, fid, (feat.xValue, feat.yValue, feat.zValue)


def find_rp(assembly, xyz, tol=10.0):
    """Key of the nearest live RP within tol of xyz, else None. Never trust stored ids (gotcha #10)."""
    best, best_d = None, None
    for _, fid, p in _rp_features(assembly):
        d = dist(p, xyz)
        if d <= tol and (best_d is None or d < best_d):
            best, best_d = fid, d
    return best


def ensure_rp(assembly, xyz, tol=10.0, set_name=None):
    """Reuse the RP near xyz or create one; optionally (re)build a named set on it. Returns the RP key."""
    key = find_rp(assembly, xyz, tol)
    if key is None:
        key = assembly.ReferencePoint(point=tuple(xyz)).id   # returns a Feature (gotcha #4)
        log('  RP created at %s (id=%d)' % (tuple(xyz), key))
    else:
        log('  RP reused at %s (id=%d)' % (tuple(xyz), key))
    if set_name:
        if set_name in assembly.sets.keys():
            del assembly.sets[set_name]
        assembly.Set(name=set_name, referencePoints=(assembly.referencePoints[key],))
    return key


def rp_region(assembly, keys):
    """regionToolset.Region over one or more RP keys (handles the 1-tuple comma, gotcha #5)."""
    if not isinstance(keys, (list, tuple)):
        keys = [keys]
    return regionToolset.Region(
        referencePoints=tuple([assembly.referencePoints[k] for k in keys]))


def list_rps(assembly):
    """List of dicts {feature, id, xyz} for all live RPs."""
    return [{'feature': n, 'id': i, 'xyz': p} for n, i, p in _rp_features(assembly)]


def find_duplicate_rps(assembly, tol=10.0):
    """Pairs (feature_a, feature_b, distance) of RPs closer than tol."""
    rps = list(_rp_features(assembly))
    out = []
    for i in range(len(rps)):
        for j in range(i + 1, len(rps)):
            d = dist(rps[i][2], rps[j][2])
            if d < tol:
                out.append((rps[i][0], rps[j][0], d))
    return out


def delete_rps_near(assembly, points, tol=10.0):
    """Delete RP features near any of points. Delete loads/constraints/sets using them FIRST (gotcha #8)."""
    names = []
    for fname, _, p in _rp_features(assembly):
        for q in points:
            if dist(p, q) <= tol:
                names.append(fname)
                break
    if names:
        assembly.deleteFeatures(tuple(names))
        log('  Deleted RP features %s' % names)
    return names
