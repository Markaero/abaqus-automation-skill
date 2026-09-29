# -*- coding: utf-8 -*-
"""Shared helpers: logging sink, report file, repository lookups, last step."""

import json
import os

_sink = [None]


def set_logger(fn):
    """Route abqlib's log messages to fn(msg) (e.g. Report.log); None = print."""
    _sink[0] = fn


def log(msg):
    """Log one line through the configured sink (default: print)."""
    if _sink[0] is not None:
        _sink[0](msg)
    else:
        print(msg)


class Report(object):
    """Report file writer: Report(path).log(msg); .data[key] = value; .close().

    Writes <path> (text) and, if .data is non-empty, <path minus ext>.json.
    Registers itself as abqlib's log sink. stdout is unreliable under noGUI,
    so this file is the authoritative output of a script.
    """

    def __init__(self, path, echo=True):
        self.path = path
        self.echo = echo
        self.data = {}
        self._f = open(path, 'w')
        set_logger(self.log)

    def log(self, msg=''):
        self._f.write('%s\n' % msg)
        self._f.flush()
        if self.echo:
            print(msg)

    def close(self):
        if self.data:
            json_path = os.path.splitext(self.path)[0] + '.json'
            f = open(json_path, 'w')
            json.dump(self.data, f, indent=1, sort_keys=True)
            f.close()
            self.log('JSON: %s' % json_path)
        self._f.close()
        set_logger(None)


def has_key(repo, name):
    """True if an Abaqus repository contains name (works on all versions)."""
    try:
        return name in repo.keys()
    except Exception:
        return False


def delete_if_exists(repo, name):
    """Delete repo[name] if present; return True if something was deleted."""
    if has_key(repo, name):
        del repo[name]
        return True
    return False


def get_last_step(model):
    """Name of the last analysis step ('Initial' is always first)."""
    names = list(model.steps.keys())
    if len(names) < 2:
        raise ValueError('model %s has no analysis step' % model.name)
    return names[-1]


def get_instance(assembly, name=None):
    """Instance by name; with name=None return the only instance or raise."""
    if name is not None:
        if not has_key(assembly.instances, name):
            raise KeyError('instance %r not found; have %s'
                           % (name, list(assembly.instances.keys())))
        return assembly.instances[name]
    keys = list(assembly.instances.keys())
    if len(keys) != 1:
        raise ValueError('pass instance name explicitly; instances = %s' % keys)
    return assembly.instances[keys[0]]


def dist(a, b):
    """Euclidean distance between two 3-sequences."""
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2) ** 0.5


def status(existed):
    """'replaced' / 'created' label for idempotent log lines."""
    return 'replaced' if existed else 'created'
