# -*- coding: utf-8 -*-
"""Model database: open/backup/save a CAE, get/copy models."""

import os
import shutil
import time

from abqlib.util import log, has_key


def open_cae(cae_path):
    """openMdb with a clear message when the CAE is locked by the GUI (gotcha #21)."""
    from abaqus import openMdb
    if not os.path.exists(cae_path):
        raise IOError('CAE not found: %s' % cae_path)
    try:
        return openMdb(pathName=cae_path)
    except Exception as exc:
        raise IOError('openMdb failed for %s (%s). If the CAE is open in the '
                      'CAE GUI, close it first.' % (cae_path, exc))


def backup_cae(cae_path):
    """Copy <cae>.<YYYYmmdd_HHMMSS>.bak next to the CAE; return the backup path."""
    dst = '%s.%s.bak' % (cae_path, time.strftime('%Y%m%d_%H%M%S'))
    shutil.copy2(cae_path, dst)
    log('Backup: %s' % dst)
    return dst


def save_cae(mdb, cae_path=None, backup=True):
    """Backup (optional) then mdb.save(). Call only after all edits succeeded."""
    path = cae_path or mdb.pathName
    if backup and path and os.path.exists(path):
        backup_cae(path)
    mdb.save()
    log('Saved %s' % path)


def get_model(mdb, name):
    """mdb.models[name] with the list of available models in the error."""
    if not has_key(mdb.models, name):
        raise KeyError('model %r not found; have %s' % (name, list(mdb.models.keys())))
    return mdb.models[name]


def copy_model(mdb, src_name, new_name, overwrite=True):
    """Deep-copy a model and regenerate its assembly. RP ids may change (gotcha #10)."""
    if has_key(mdb.models, new_name):
        if not overwrite:
            raise ValueError('model %r already exists' % new_name)
        del mdb.models[new_name]
    model = mdb.Model(name=new_name, objectToCopy=get_model(mdb, src_name))
    model.rootAssembly.regenerate()
    log('Copied model %s -> %s' % (src_name, new_name))
    return model
