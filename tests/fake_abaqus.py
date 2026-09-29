"""Minimal fake Abaqus modules + model objects so abqlib logic can be unit-tested
with plain Python 3. Only what abqlib touches is modelled; this does not prove
the real Abaqus API accepts the calls - run a real smoke test for that."""

import sys
import types


class Const(object):
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return self.name


_CONSTS = ['ON', 'OFF', 'UNSET', 'UNIFORM', 'FIELD', 'DISTRIBUTING', 'KINEMATIC',
           'WHOLE_SURFACE', 'ROTATIONAL_STRUCTURAL', 'CYLINDRICAL', 'SPECIFIED',
           'TOTAL_MASS', 'MASS_PROPORTIONAL', 'ANALYSIS', 'PERCENTAGE']


class Region(object):
    def __init__(self, **kw):
        self.kw = kw


def install():
    consts = types.ModuleType('abaqusConstants')
    for c in _CONSTS:
        setattr(consts, c, Const(c))
    rt = types.ModuleType('regionToolset')
    rt.Region = Region
    sys.modules['abaqusConstants'] = consts
    sys.modules['regionToolset'] = rt
    sys.modules['caeModules'] = types.ModuleType('caeModules')
    ab = types.ModuleType('abaqus')
    ab.openMdb = lambda pathName: 'MDB:' + pathName
    sys.modules['abaqus'] = ab
    return consts


class Repo(dict):
    def keys(self):
        return list(dict.keys(self))


class Obj(object):
    def __init__(self, **kw):
        self.__dict__.update(kw)


class Feature(Obj):
    pass


class Assembly(object):
    def __init__(self, log):
        self.features = Repo()
        self.referencePoints = Repo()
        self.sets = Repo()
        self.surfaces = Repo()
        self.instances = Repo()
        self.engineeringFeatures = Obj(inertias=Repo(), PointMassInertia=self._pmi)
        self._next = 1
        self.log = log

    def ReferencePoint(self, point):
        fid = self._next
        self._next += 1
        f = Feature(id=fid, xValue=point[0], yValue=point[1], zValue=point[2])
        self.features['RP-%d' % fid] = f
        self.referencePoints[fid] = Obj(id=fid)
        return f

    def add_datum_point(self, name, xyz):
        fid = self._next
        self._next += 1
        self.features[name] = Feature(id=fid, xValue=xyz[0], yValue=xyz[1], zValue=xyz[2])

    def Set(self, name, **kw):
        self.sets[name] = Obj(name=name, **kw)
        return self.sets[name]

    def Surface(self, name, **kw):
        self.surfaces[name] = Obj(name=name, **kw)
        return self.surfaces[name]

    def deleteFeatures(self, names):
        for n in names:
            self.log.append(('del_feature', n))
            fid = self.features[n].id
            del self.features[n]
            del self.referencePoints[fid]

    def _pmi(self, **kw):
        self.engineeringFeatures.inertias[kw['name']] = Obj(**kw)
        return self.engineeringFeatures.inertias[kw['name']]


class LoggingRepo(Repo):
    def __init__(self, tag, log):
        Repo.__init__(self)
        self.tag, self.log = tag, log

    def __delitem__(self, k):
        self.log.append(('del_' + self.tag, k))
        Repo.__delitem__(self, k)


class Model(object):
    def __init__(self, name='M', steps=('Initial', 'Step-1')):
        self.name = name
        self.dellog = []
        self.rootAssembly = Assembly(self.dellog)
        self.rootAssembly.sets = LoggingRepo('set', self.dellog)
        self.rootAssembly.surfaces = LoggingRepo('surface', self.dellog)
        self.rootAssembly.engineeringFeatures.inertias = LoggingRepo('inertia', self.dellog)
        self.loads = LoggingRepo('load', self.dellog)
        self.constraints = LoggingRepo('constraint', self.dellog)
        self.boundaryConditions = Repo()
        self.steps = Repo()
        for s in steps:
            self.steps[s] = Obj(name=s, loadStates=Repo())
        self.calls = []

    def _make(self, repo, kind):
        def f(**kw):
            self.calls.append((kind, kw))
            o = Obj(kind=kind, **kw)
            repo[kw['name']] = o
            return o
        return f

    def __getattr__(self, attr):
        table = {'ConcentratedForce': 'loads', 'Moment': 'loads', 'Pressure': 'loads',
                 'Gravity': 'loads', 'InertiaRelief': 'loads', 'Coupling': 'constraints',
                 'Equation': 'constraints', 'DisplacementBC': 'boundaryConditions',
                 'EncastreBC': 'boundaryConditions'}
        if attr in table:
            return self._make(getattr(self, table[attr]), attr)
        raise AttributeError(attr)
