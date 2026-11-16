import importlib
import os
import sys
import unittest
from types import SimpleNamespace as NS

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


class Command:
    error = ValueError

    def __init__(self, **params):
        self.params = params
        self.messages = []

    def get(self, key, default=None):
        return self.params.get(key, default)

    def get_command_parameters(self):
        return dict(self.params)

    def respond_info(self, text):
        self.messages.append(text)


class RoughTests(unittest.TestCase):
    def setUp(self):
        self.mod = importlib.import_module('rough_z_tilt')
        self.helper = NS(probe_points=[(10., 10.), (60., 110.), (110., 10.)],
                         speed=300., use_offsets=False)
        self.applied = NS(applied=True)
        self.applied.reset = lambda: setattr(self.applied, 'applied', False)
        self.calls = []

        def native(cmd):
            self.calls.append((list(self.helper.probe_points), self.helper.speed,
                               cmd.get_command_parameters()))
            self.applied.applied = True

        self.tilt = NS(probe_helper=self.helper, z_status=self.applied,
                       z_positions=[(-20, -20), (60, 150), (140, -20)],
                       cmd_Z_TILT_ADJUST=native)
        self.status = dict(homed_axes='xyz', axis_minimum=(-10, -10, -10),
                           axis_maximum=(140, 130, 120))
        self.objects = {
            'toolhead': NS(get_status=lambda t: self.status),
            'probe': NS(get_offsets=lambda *args: (5., 7., 0.)),
            'gcode': NS(create_gcode_command=lambda a, b, p: Command(**p)),
        }
        printer = NS(lookup_object=lambda name, default=None: self.objects.get(name, default),
                     get_reactor=lambda: NS(monotonic=lambda: 0.))
        self.rough = self.mod.RoughZTilt.__new__(self.mod.RoughZTilt)
        self.rough.printer = printer
        self.rough.tilt = self.tilt
        self.rough.scale = 1. / 3.
        self.rough.center = (60., 60.)
        self.rough.speed = 80.
        self.rough.horizontal_move_z = 12.
        self.rough.retries = 3
        self.rough.retry_tolerance = .1

    def test_contraction_and_translation(self):
        for size in (120., 300., 1000.):
            points = [(0., 0.), (size, 0.), (size / 2, size)]
            for shift in (0., -300.):
                shifted = [(x + shift, y + shift) for x, y in points]
                result = self.mod.contract_points(shifted, .25)
                center = (size / 2 + shift, size / 3 + shift)
                for p, q in zip(shifted, result):
                    for i in (0, 1):
                        self.assertAlmostEqual(q[i] - center[i], .25 * (p[i] - center[i]))

    def test_two_motor_points(self):
        result = self.mod.contract_points([(0, 20), (100, 20)], 1 / 3)
        self.assertAlmostEqual(result[0][0], 100 / 3)

    def test_invalid_geometry_and_numbers(self):
        for scale in (0, -1, 1, 2, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                self.mod.contract_points([(0, 0), (100, 100)], scale)
        for points in ([(0, 0)], [(0, 0), (0, 0)], [(0, 0), (float('nan'), 2)]):
            with self.assertRaises(ValueError):
                self.mod.contract_points(points, .3)
        with self.assertRaises(ValueError):
            self.mod.contract_points([(0, 0), (100, 100)], .3, (float('inf'), 0))

    def test_preview_never_calls_native_or_requires_homing(self):
        self.status['homed_axes'] = ''
        cmd = Command()
        original = self.helper.probe_points
        self.rough.cmd_ROUGH_Z_TILT_PREVIEW(cmd)
        self.assertFalse(self.calls)
        self.assertIs(original, self.helper.probe_points)
        self.assertIn('43.333', '\n'.join(cmd.messages))
        self.assertTrue(self.applied.applied)

    def test_native_pass_preserves_pivots_and_restores_helper(self):
        original = self.helper.probe_points
        pivots = self.tilt.z_positions
        self.rough.cmd_ROUGH_Z_TILT(Command(SAMPLES='2'))
        self.assertAlmostEqual(self.calls[0][0][0][0], 43.3333333333)
        self.assertEqual(self.calls[0][1], 80.)
        self.assertEqual(self.calls[0][2]['SAMPLES'], '2')
        self.assertEqual(float(self.calls[0][2]['RETRY_TOLERANCE']), .1)
        self.assertIs(original, self.helper.probe_points)
        self.assertIs(pivots, self.tilt.z_positions)
        self.assertEqual(self.helper.speed, 300.)
        self.assertFalse(self.applied.applied)

    def test_restore_after_probe_or_retry_failure(self):
        original = self.helper.probe_points
        def fail(cmd):
            self.applied.applied = True
            raise RuntimeError('probe/retry failed')
        self.tilt.cmd_Z_TILT_ADJUST = fail
        with self.assertRaisesRegex(RuntimeError, 'probe/retry failed'):
            self.rough.cmd_ROUGH_Z_TILT(Command())
        self.assertIs(original, self.helper.probe_points)
        self.assertEqual(self.helper.speed, 300.)
        self.assertFalse(self.applied.applied)

    def test_rejects_unhomed_manual_missing_probe_and_nonfinite_before_mutation(self):
        for params in ({'METHOD': 'manual'}, {'SCALE': 'nan'}, {'SPEED': 'inf'},
                       {'HORIZONTAL_MOVE_Z': '-1'}, {'CENTER': '0,nan'},
                       {'RETRY_TOLERANCE': 'nan'}, {'RETRIES': '0'}):
            with self.assertRaises(ValueError):
                self.rough.cmd_ROUGH_Z_TILT(Command(**params))
        self.status['homed_axes'] = 'xy'
        with self.assertRaises(ValueError):
            self.rough.cmd_ROUGH_Z_TILT(Command())
        self.status['homed_axes'] = 'xyz'
        del self.objects['probe']
        with self.assertRaises(ValueError):
            self.rough.cmd_ROUGH_Z_TILT(Command())
        self.assertFalse(self.calls)
        self.assertTrue(self.applied.applied)

    def test_bounds_respect_helper_offset_mode(self):
        self.helper.probe_points = [(0., 0.), (100., 100.)]
        self.tilt.z_positions = [(0, 0), (100, 100)]
        self.status['axis_minimum'] = (32., 30., -10.)
        self.rough.center = (50., 50.)
        self.rough.cmd_ROUGH_Z_TILT(Command())
        self.helper.use_offsets = True
        with self.assertRaisesRegex(ValueError, 'bounds'):
            self.rough.cmd_ROUGH_Z_TILT(Command())


if __name__ == '__main__':
    unittest.main()
