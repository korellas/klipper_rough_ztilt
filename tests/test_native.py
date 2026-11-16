"""Optional integration with real Klipper classes; no MCU or physical motion.

KLIPPER_PATH=/path/to/klipper python3 -m unittest discover -s tests -v
Only hardware-facing services are simulated. Helper/retries/solver are native.
"""
import ast
import importlib.util
import inspect
import logging
import os
import sys
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
from collections import namedtuple

import test_rough_z_tilt as base

Command = base.Command


def native_classes(path):
    sys.path.insert(0, str(path))
    spec = importlib.util.spec_from_file_location('native_mathutil', path / 'mathutil.py')
    mathutil = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mathutil)
    scope = dict(logging=logging, mathutil=mathutil,
                 manual_probe=NS(verify_no_manual_probe=lambda p: None))
    for filename, names in [('probe.py', ['ProbePointsHelper']),
                             ('z_tilt.py', ['RetryHelper', 'ZAdjustStatus', 'ZTilt'])]:
        tree = ast.parse((path / 'extras' / filename).read_text())
        tree.body = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name in names]
        exec(compile(tree, filename, 'exec'), scope)
        scope['probe'] = NS(ProbePointsHelper=scope['ProbePointsHelper'])
    return scope


@unittest.skipUnless(os.environ.get('KLIPPER_PATH'), 'Set KLIPPER_PATH for native integration')
class NativeIntegration(unittest.TestCase):
    def test_actual_helper_and_solver_keep_physical_pivots(self):
        fixture = base.RoughTests()
        fixture.setUp()
        rough = fixture.rough
        classes = native_classes(Path(os.environ['KLIPPER_PATH']) / 'klippy')
        helper = classes['ProbePointsHelper'].__new__(classes['ProbePointsHelper'])
        helper.__dict__.update(fixture.helper.__dict__)
        helper.default_horizontal_move_z = 8.
        helper.printer = rough.printer
        helper.gcode = fixture.objects['gcode']
        helper.lift_speed = 5.
        tilt = classes['ZTilt'].__new__(classes['ZTilt'])
        tilt.__dict__.update(fixture.tilt.__dict__)
        tilt.printer = rough.printer
        tilt.probe_helper = helper
        tilt.z_status = NS(reset=lambda: setattr(fixture.applied, 'applied', False),
                           check_retry_result=lambda r: r)
        retry = classes['RetryHelper'].__new__(classes['RetryHelper'])
        retry.default_max_retries = 3
        retry.default_retry_tolerance = .1
        retry.gcode = NS(respond_info=lambda t: None, error=ValueError)
        retry.value_label = 'range'
        retry.error_msg_extra = ''
        tilt.retry_helper = retry
        adjustments = []
        tilt.z_helper = NS(adjust_steppers=lambda values, speed: adjustments.append(values))
        # Remove instance-level stub so the actual native command method runs.
        del tilt.cmd_Z_TILT_ADJUST
        helper.finalize_callback = tilt.probe_finalize
        rough.tilt = tilt
        moves = []
        pos = [60., 60., 12.]
        def move(coord, speed):
            moves.append((list(coord), speed))
            for i, value in enumerate(coord):
                if value is not None:
                    pos[i] = value
        helper._move = move
        fixture.objects['toolhead'].get_last_move_time = lambda: 0.
        results = []
        def run_probe(cmd):
            z = .02 * pos[0] - .015 * pos[1] if not adjustments else 0.
            if len(inspect.signature(tilt.probe_finalize).parameters) == 2:
                results.append([pos[0], pos[1], z])
            else:
                result_type = namedtuple('ProbeResult', 'bed_x bed_y bed_z')
                results.append(result_type(pos[0], pos[1], z))
        def pull():
            data = list(results)
            results.clear()
            return data
        fixture.objects['probe'] = NS(
            get_offsets=lambda *args: (0., 0., 0.),
            get_probe_params=lambda cmd: {'lift_speed': 5.},
            start_probe_session=lambda cmd: NS(run_probe=run_probe,
                pull_probed_results=pull, end_probe_session=lambda: None))
        # Use actual native numeric parameter constraints in the fake command API.
        def get_float(cmd, key, default, **kw):
            value = float(cmd.get(key, default))
            if value < kw.get('minval', -float('inf')) or value > kw.get('maxval', float('inf')):
                raise ValueError(key)
            return value
        Command.get_float = get_float
        Command.get_int = lambda cmd, key, default, **kw: int(get_float(cmd, key, default, **kw))
        original = helper.probe_points
        rough.cmd_ROUGH_Z_TILT(Command())
        self.assertGreaterEqual(len(adjustments), 1)
        # The narrow scan must still correct across the FULL physical pivot spacing.
        pivots = tilt.z_positions
        expected = .02 * (pivots[2][0] - pivots[0][0]) - .015 * (pivots[2][1] - pivots[0][1])
        self.assertAlmostEqual(adjustments[0][2] - adjustments[0][0], expected, places=3)
        self.assertIs(helper.probe_points, original)
        self.assertEqual(helper.speed, 300.)
        self.assertEqual(moves[0][0][2], 12.)


if __name__ == '__main__':
    unittest.main()
