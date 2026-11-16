# klipper_rough_ztilt

A probe-independent central coarse pass for Klipper's native `[z_tilt]`.
It contracts existing measurement points by one third, runs the native solver
against the unchanged physical motor pivots, then restores the original points.
Your existing macro runs normal full-area tilt afterward.

## Installation

Clone this repository on the Klipper host and run `sh install.sh ~/klipper`.
Include [examples/rough_z_tilt.cfg](examples/rough_z_tilt.cfg), then restart
Klipper while idle. Existing `[z_tilt]` and an automatic probe are required.
No firmware flashing, Python dependencies, or Klipper source patches are needed.

## Commands and integration

`ROUGH_Z_TILT_PREVIEW` reports contracted points without homing, heating, or
moving. `ROUGH_Z_TILT` performs only the coarse pass and requires XYZ homed.
Both accept `SCALE=0.3333333333333333 CENTER=x,y SPEED=80 HORIZONTAL_MOVE_Z=12
RETRIES=3 RETRY_TOLERANCE=0.1` on one line. Center defaults to the arithmetic
mean of native measurement points; speed and travel height default to native
settings. Scale must be strictly between 0 and 1. Other native probe parameters,
such as `SAMPLES`, pass through to Klipper.

Insert `ROUGH_Z_TILT` immediately before the native full-area command in your
existing tilt wrapper, after homing and probe preparation. For a wrapper using
`rename_existing: _Z_TILT_ADJUST_BASE`, the sequence is:

```gcode
ROUGH_Z_TILT
_Z_TILT_ADJUST_BASE
```

Keep probe docking, TAP temperature management, mesh clearing and any Z rehome
in printer macros. Also wrap direct calls to the rough command if your probe
needs such preparation (use `rename_existing: _ROUGH_Z_TILT_BASE`, and call that
base from an already protected full-tilt wrapper to avoid nested state saves).
A rough failure stops the sequence; original points and speed are restored in
`finally`. The rough pass always clears `z_tilt.applied`; only full-area leveling
should establish completion. Manual probing is rejected.

## Limits and verification

Two or more independent Z motors are supported through native ZTilt. There are
no bed sizes or probe brands embedded in the extension. At 1/3 spacing, height
measurement errors have a larger effect on inferred slope; the following
full-area pass provides final precision. This cannot guarantee clearance for
arbitrary tilt or fix collisions during XY homing before leveling.

Run `python3 -m unittest discover -s tests -v`. Set `KLIPPER_PATH` to a Klipper
checkout to additionally run native helper/retry/solver integration. This test
simulates hardware and checks full pivot-span adjustments. Tested with Pandora's
Klipper 0.12 and current master sources on 2026-11-16. Physical probe-brand
verification is still pending.

To update, pull the deployed branch and restart Klipper while idle. To remove,
remove the rough call and config section, unlink
`~/klipper/klippy/extras/rough_z_tilt.py`, and restart.

GPL-3.0-or-later. See [design](docs/design.md) and [work order](docs/WORK_ORDER.md).
