# Rough leveling using Klipper's native ZTilt solver and probe interface.
# SPDX-License-Identifier: GPL-3.0-or-later
import math


def number(value, label, low=None, high=None):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError('%s must be finite' % label)
    if low is not None and result < low:
        raise ValueError('%s is below its minimum' % label)
    if high is not None and result > high:
        raise ValueError('%s is above its maximum' % label)
    return result


def xy(value):
    if isinstance(value, str):
        value = value.split(',')
    if len(value) != 2:
        raise ValueError('Expected two XY coordinates')
    return tuple(number(v, 'coordinate') for v in value)


def contract_points(points, scale, center=None):
    scale = number(scale, 'scale')
    if not 0 < scale < 1:
        raise ValueError('scale must be greater than zero and less than one')
    points = [xy(p) for p in points]
    if len(set(points)) < 2:
        raise ValueError('Need at least two distinct measurement points')
    if center is None:
        center = tuple(sum(p[i] for p in points) / len(points) for i in (0, 1))
    center = xy(center)
    result = [tuple(center[i] + scale * (p[i] - center[i]) for i in (0, 1))
              for p in points]
    # Overflow and floating-point collapse must not reach the native solver.
    result = [xy(p) for p in result]
    if len(set(result)) < 2:
        raise ValueError('Contracted measurement points collapse')
    return result


class RoughZTilt:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.tilt = self.printer.load_object(config, 'z_tilt')
        self.scale = config.getfloat('scale', 1. / 3., above=0., below=1.)
        center = config.get('center', None)
        try:
            self.center = None if center is None else xy(center)
            self.speed = config.getfloat('speed', self.tilt.probe_helper.speed,
                                         above=0.)
            self.horizontal_move_z = config.getfloat(
                'horizontal_move_z',
                self.tilt.probe_helper.default_horizontal_move_z, above=0.)
            self.retries = config.getint('retries', 3, minval=1, maxval=30)
            self.retry_tolerance = config.getfloat('retry_tolerance', .1,
                                                   above=0., maxval=1.)
            contract_points(self.tilt.probe_helper.probe_points,
                            self.scale, self.center)
            for val in (self.speed, self.horizontal_move_z, self.retry_tolerance):
                number(val, 'configuration')
        except (ValueError, TypeError) as exc:
            raise config.error(str(exc))
        gcode = self.printer.lookup_object('gcode')
        gcode.register_command('ROUGH_Z_TILT', self.cmd_ROUGH_Z_TILT,
                               desc='Level using contracted native Z tilt points')
        gcode.register_command('ROUGH_Z_TILT_PREVIEW',
                               self.cmd_ROUGH_Z_TILT_PREVIEW,
                               desc='Report rough points without moving')

    def _settings(self, gcmd):
        try:
            center = gcmd.get('CENTER', self.center)
            points = contract_points(self.tilt.probe_helper.probe_points,
                                     gcmd.get('SCALE', self.scale), center)
            if len(self.tilt.z_positions) > 2:
                a = points[0]
                # A plane requires non-collinear points. Two-motor setups do not.
                area = max(abs((b[0] - a[0]) * (c[1] - a[1])
                               - (b[1] - a[1]) * (c[0] - a[0]))
                           for b in points[1:] for c in points[1:])
                if area <= 1.e-9:
                    raise ValueError('Three or more motors need non-collinear points')
            speed = number(gcmd.get('SPEED', self.speed), 'speed', 1.e-9)
            height = number(gcmd.get('HORIZONTAL_MOVE_Z', self.horizontal_move_z),
                            'horizontal_move_z', 1.e-9)
            tolerance = number(gcmd.get('RETRY_TOLERANCE', self.retry_tolerance),
                               'retry_tolerance', 1.e-9, 1.)
            retries = int(gcmd.get('RETRIES', self.retries))
            if not 1 <= retries <= 30:
                raise ValueError('retries must be between 1 and 30')
        except (ValueError, TypeError, OverflowError) as exc:
            raise gcmd.error(str(exc))
        return points, speed, height, tolerance, retries

    def cmd_ROUGH_Z_TILT_PREVIEW(self, gcmd):
        points, speed, height, tolerance, retries = self._settings(gcmd)
        gcmd.respond_info('Rough Z tilt: speed=%.3f height=%.3f '
                          'tolerance=%.3f retries=%d\n%s' % (
                              speed, height, tolerance, retries,
                              '\n'.join('  %.3f, %.3f' % p for p in points)))

    def cmd_ROUGH_Z_TILT(self, gcmd):
        points, speed, height, tolerance, retries = self._settings(gcmd)
        if gcmd.get('METHOD', 'automatic').lower() != 'automatic':
            raise gcmd.error('ROUGH_Z_TILT requires METHOD=automatic')
        probe = self.printer.lookup_object('probe', None)
        if probe is None:
            raise gcmd.error('ROUGH_Z_TILT requires an automatic probe')
        toolhead = self.printer.lookup_object('toolhead')
        status = toolhead.get_status(self.printer.get_reactor().monotonic())
        if not all(axis in status['homed_axes'] for axis in 'xyz'):
            raise gcmd.error('Home XYZ before ROUGH_Z_TILT')
        helper = self.tilt.probe_helper
        if not status['axis_minimum'][2] <= height <= status['axis_maximum'][2]:
            raise gcmd.error('Rough travel height is outside Z bounds')
        offsets = (0., 0.)
        if helper.use_offsets:
            # Old Klipper get_offsets() and current get_offsets(gcmd) both work.
            import inspect
            if inspect.signature(probe.get_offsets).parameters:
                offsets = probe.get_offsets(gcmd)[:2]
            else:
                offsets = probe.get_offsets()[:2]
        for point in points:
            for axis in (0, 1):
                coord = point[axis] - offsets[axis]
                if not (math.isfinite(coord) and
                        status['axis_minimum'][axis] <= coord <=
                        status['axis_maximum'][axis]):
                    raise gcmd.error('Rough nozzle point is outside axis bounds')
        params = dict(gcmd.get_command_parameters())
        for name in ('SCALE', 'CENTER', 'SPEED'):
            params.pop(name, None)
        params.update(METHOD='automatic', HORIZONTAL_MOVE_Z=str(height),
                      RETRIES=str(retries), RETRY_TOLERANCE=str(tolerance))
        native_cmd = self.printer.lookup_object('gcode').create_gcode_command(
            'Z_TILT_ADJUST', 'Z_TILT_ADJUST', params)
        old_points, old_speed = helper.probe_points, helper.speed
        try:
            helper.probe_points, helper.speed = points, speed
            self.tilt.cmd_Z_TILT_ADJUST(native_cmd)
        finally:
            helper.probe_points, helper.speed = old_points, old_speed
            self.tilt.z_status.reset()


def load_config(config):
    return RoughZTilt(config)
