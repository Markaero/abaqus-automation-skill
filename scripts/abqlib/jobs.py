# -*- coding: utf-8 -*-
"""Jobs: create/submit/wait, skip-if-done, success check from .sta, write .inp."""

import os

from abaqusConstants import ANALYSIS, OFF, PERCENTAGE

from abqlib.util import log, has_key


def job_succeeded(job_name, work_dir='.'):
    """True/False from <job>.sta ('COMPLETED SUCCESSFULLY'), None if no .sta. job.status is unreliable in noGUI."""
    sta = os.path.join(work_dir, '%s.sta' % job_name)
    if not os.path.exists(sta):
        return None
    f = open(sta)
    text = f.read()
    f.close()
    if 'HAS COMPLETED SUCCESSFULLY' in text:
        return True
    return False


def run_job(mdb, job_name, model_name, work_dir=None, cpus=4, skip_if_done=True,
            memory_pct=90, **job_kw):
    """Submit and wait. Skips if <job>.odb exists and .sta says success. Returns True/False/None (see job_succeeded)."""
    old = os.getcwd()
    if work_dir:
        os.chdir(work_dir)   # job artifacts land in cwd
    try:
        if skip_if_done and os.path.exists('%s.odb' % job_name) and job_succeeded(job_name):
            log('  Job %s: .odb exists and succeeded - skipped' % job_name)
            return True
        if has_key(mdb.jobs, job_name):
            del mdb.jobs[job_name]
        job = mdb.Job(name=job_name, model=model_name, type=ANALYSIS,
                      numCpus=cpus, numDomains=cpus,
                      memory=memory_pct, memoryUnits=PERCENTAGE, **job_kw)
        log('  Job %s submitted (%d cpus)' % (job_name, cpus))
        job.submit(consistencyChecking=OFF)
        job.waitForCompletion()
        ok = job_succeeded(job_name)
        log('  Job %s finished: %s' % (job_name,
                                       {True: 'SUCCESS', False: 'FAILED (read .msg/.dat)',
                                        None: 'no .sta'}[ok]))
        return ok
    finally:
        os.chdir(old)


def write_input(mdb, job_name, model_name, work_dir=None):
    """Write <job>.inp without running (to grep SPOS/SNEG, check keywords, etc.)."""
    old = os.getcwd()
    if work_dir:
        os.chdir(work_dir)
    try:
        if has_key(mdb.jobs, job_name):
            del mdb.jobs[job_name]
        mdb.Job(name=job_name, model=model_name, type=ANALYSIS).writeInput(consistencyChecking=OFF)
        path = os.path.join(os.getcwd(), '%s.inp' % job_name)
        log('  Wrote %s' % path)
        return path
    finally:
        os.chdir(old)
