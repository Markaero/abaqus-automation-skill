"""Unit tests for abqlib logic against fake Abaqus objects.

    python3 -m unittest discover -s tests
"""

import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'scripts'))

import fake_abaqus  # noqa: E402
C = fake_abaqus.install()

from abqlib import rp, mass, loads, constraints, bcs, cleanup, job, util  # noqa: E402

util.set_logger(lambda msg: None)


class RPTests(unittest.TestCase):
    def setUp(self):
        self.m = fake_abaqus.Model()
        self.a = self.m.rootAssembly

    def test_find_nearest_and_ignore_datum_points(self):
        self.a.add_datum_point('Datum pt-1', (0, 0, 0))
        k1 = self.a.ReferencePoint((5, 0, 0)).id
        k2 = self.a.ReferencePoint((1, 0, 0)).id
        self.assertEqual(rp.find_rp(self.a, (0, 0, 0), tol=10), k2)
        self.assertEqual(rp.find_rp(self.a, (4.9, 0, 0), tol=10), k1)
        self.assertIsNone(rp.find_rp(self.a, (100, 0, 0), tol=10))

    def test_ensure_rp_reuses_and_builds_set(self):
        k = rp.ensure_rp(self.a, (0, 0, 0), set_name='S')
        k2 = rp.ensure_rp(self.a, (0.5, 0, 0), set_name='S')
        self.assertEqual(k, k2)
        self.assertEqual(len(self.a.referencePoints), 1)
        self.assertEqual(len(self.a.sets['S'].referencePoints), 1)

    def test_duplicates(self):
        self.a.ReferencePoint((0, 0, 0))
        self.a.ReferencePoint((3, 0, 0))
        self.assertEqual(len(rp.find_duplicate_rps(self.a, tol=10)), 1)


class MassTests(unittest.TestCase):
    def test_point_mass_is_split_per_rp(self):
        m = fake_abaqus.Model()
        a = m.rootAssembly
        keys = [a.ReferencePoint((i * 100, 0, 0)).id for i in range(4)]
        mass.ensure_point_mass(a, 'Fins', keys, total_mass=0.4)
        self.assertAlmostEqual(a.engineeringFeatures.inertias['Fins'].mass, 0.1)
        mass.ensure_point_mass(a, 'Fins', keys, total_mass=0.8)   # idempotent
        self.assertAlmostEqual(a.engineeringFeatures.inertias['Fins'].mass, 0.2)


class LoadTests(unittest.TestCase):
    def setUp(self):
        self.m = fake_abaqus.Model()

    def test_cforce_defaults_and_replace(self):
        loads.ensure_cforce(self.m, 'F', 'region', (100.0, None, 0.0))
        kw = self.m.calls[-1][1]
        self.assertEqual(kw['createStepName'], 'Step-1')
        self.assertEqual(kw['cf1'], 100.0)
        self.assertNotIn('cf2', kw)
        self.assertIs(kw['follower'], C.OFF)
        loads.ensure_cforce(self.m, 'F', 'region', (200.0, 0, 0), follower=True)
        self.assertEqual(len(self.m.loads), 1)
        self.assertIn(('del_load', 'F'), self.m.dellog)

    def test_zero_force_rejected(self):
        self.assertRaises(ValueError, loads.ensure_cforce, self.m, 'F', 'r', (0, 0, 0))

    def test_pressure_field(self):
        loads.ensure_pressure(self.m, 'P', 'surf', -1.0, field='Aero')
        kw = self.m.calls[-1][1]
        self.assertIs(kw['distributionType'], C.FIELD)
        self.assertEqual(kw['field'], 'Aero')

    def test_load_values_skip_unset(self):
        self.m.steps['Step-1'].loadStates['F'] = fake_abaqus.Obj(cf1=5.0, cf2=C.UNSET, cf3=None)
        self.assertEqual(loads.load_values(self.m, 'F'), {'cf1': 5.0})


class ConstraintTests(unittest.TestCase):
    def setUp(self):
        self.m = fake_abaqus.Model()
        self.k = self.m.rootAssembly.ReferencePoint((0, 0, 0)).id

    def test_distributing_beam_ring(self):
        constraints.ensure_coupling(self.m, 'C', self.k, 'ring', beam_ring=True)
        kw = self.m.calls[-1][1]
        self.assertIs(kw['couplingType'], C.DISTRIBUTING)
        self.assertIs(kw['rotationalCouplingType'], C.ROTATIONAL_STRUCTURAL)
        self.assertEqual(len(kw['controlPoint'].kw['referencePoints']), 1)

    def test_kinematic_has_no_weighting(self):
        constraints.ensure_coupling(self.m, 'C', self.k, 'surf', kind='kinematic')
        kw = self.m.calls[-1][1]
        self.assertIs(kw['couplingType'], C.KINEMATIC)
        self.assertNotIn('weightingMethod', kw)

    def test_tie_falls_back_to_master_slave(self):
        seen = []

        def old_tie(**kw):
            if 'main' in kw:
                raise TypeError('keyword error')
            seen.append(kw)
            return kw
        self.m.Tie = old_tie
        constraints.ensure_tie(self.m, 'T', 'a', 'b')
        self.assertEqual(seen[0]['master'], 'a')

    def test_pair_equations_names_and_csys(self):
        names = constraints.pair_equations(self.m, 'Eq', [('a1', 'b1')], dofs=(1, 2), csys_id=7)
        self.assertEqual(names, ['Eq_D1_1', 'Eq_D2_1'])
        self.assertEqual(self.m.calls[-1][1]['terms'][0], (1.0, 'a1', 2, 7))


class BCTests(unittest.TestCase):
    def test_none_is_unset(self):
        m = fake_abaqus.Model()
        bcs.ensure_displacement_bc(m, 'BC', 'r', u=(0, None, 0, None, None, None))
        kw = m.calls[-1][1]
        self.assertEqual(kw['u1'], 0.0)
        self.assertIs(kw['u2'], C.UNSET)


class CleanupTests(unittest.TestCase):
    def test_delete_order(self):
        m = fake_abaqus.Model()
        a = m.rootAssembly
        k = rp.ensure_rp(a, (0, 0, 0), set_name='S')
        loads.ensure_cforce(m, 'F', a.sets['S'], (1, 0, 0))
        constraints.ensure_coupling(m, 'C', k, 'surf')
        a.Surface(name='Surf')
        del m.dellog[:]
        cleanup.delete_in_order(m, loads=['F', 'missing'], constraints=['C'],
                                sets=['S'], surfaces=['Surf'], rp_points=[(0, 0, 0)])
        kinds = [e[0] for e in m.dellog]
        self.assertEqual(kinds, ['del_load', 'del_constraint', 'del_set',
                                 'del_surface', 'del_feature'])


def _write(path, text):
    with open(path, 'w') as f:
        f.write(text)


def _read(path):
    with open(path) as f:
        return f.read()


class JobTests(unittest.TestCase):
    def test_sta_parsing(self):
        d = tempfile.mkdtemp()
        self.assertIsNone(job.job_succeeded('J', d))
        _write(os.path.join(d, 'J.sta'), '...\n THE ANALYSIS HAS COMPLETED SUCCESSFULLY\n')
        self.assertTrue(job.job_succeeded('J', d))
        _write(os.path.join(d, 'K.sta'), 'THE ANALYSIS HAS NOT BEEN COMPLETED\n')
        self.assertFalse(job.job_succeeded('K', d))


class UtilTests(unittest.TestCase):
    def test_last_step(self):
        self.assertEqual(util.get_last_step(fake_abaqus.Model()), 'Step-1')
        self.assertRaises(ValueError, util.get_last_step, fake_abaqus.Model(steps=('Initial',)))

    def test_report_writes_text_and_json(self):
        d = tempfile.mkdtemp()
        r = util.Report(os.path.join(d, '_x.txt'), echo=False)
        util.log('hello')
        r.data['a'] = 1
        r.close()
        self.assertIn('hello', _read(os.path.join(d, '_x.txt')))
        self.assertTrue(os.path.exists(os.path.join(d, '_x.json')))
        util.set_logger(lambda msg: None)


if __name__ == '__main__':
    unittest.main()
