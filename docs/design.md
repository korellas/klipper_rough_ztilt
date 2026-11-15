# Rough Z tilt

Build a probe-independent companion to Klipper's existing `[z_tilt]`.
Contract its configured measurement points around a configurable center by
`center + scale * (point - center)`, default scale 1/3. If no center is
specified, use the arithmetic mean of the original measurement points.
Do not change the physical motor pivot coordinates or duplicate the leveling solver.

`ROUGH_Z_TILT` performs only the contracted pass. Existing macros then call
their normal full-size Z tilt command. `ROUGH_Z_TILT_PREVIEW` reports the
coordinates without homing, probing, heating or moving. The extension never
homes or activates a dockable probe on its own: existing printer macros own
that workflow.

Use the native ZTilt object's command method and ProbePointsHelper. This avoids
depending on old versus new probe result formats or a particular probe brand.
Automatic probe sessions only: manual interactive probing cannot be safely
wrapped in synchronous restoration and is rejected before changing anything.
Restore points and travel speed in `finally` on success or failure; clear
`z_tilt.applied` after a rough pass, leaving full-size leveling responsible for
asserting completion. Reject invalid geometry/scales and require XYZ homed for
the motion command. Bounds checking uses the native helper's XY-offset mode.

Pandora2 integration: preserve Klippain's homing, probe activation, acceleration,
LED and full tilt workflow, inserting one rough pass directly before the base
full tilt call. Printer-specific center and speeds belong in its config only.
Never run physical leveling automatically during installation.
