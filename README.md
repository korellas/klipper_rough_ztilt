# klipper_rough_ztilt

Planning repository for a probe-independent rough Z tilt companion to Klipper.
**No extension is implemented or installed yet.** Development is deferred while
Pandora2's standalone configuration is prepared.

Read [the work order](docs/WORK_ORDER.md), [design](docs/design.md), and
[implementation plan](docs/plan.md).

The intended workflow contracts the printer's existing `[z_tilt]` measurement
points to one third around a chosen center, runs a coarse adjustment, then lets
the existing normal full-area tilt finish the job. Bed dimensions, pivot
positions and probe hardware are not hardcoded.
