# Implementation plan

Status: deferred by the user. This repository currently contains work
instructions only. Do not implement or install the extension as part of the
Pandora2 standalone configuration migration.

1. Add unittest cases for contraction on different printer sizes, two and three
   Z systems, invalid numeric input, actual native helper compatibility,
   synchronous restoration after errors, rough completion state, dry preview,
   probe offsets, homing requirements, and rejected manual probing.
2. Run tests before implementation and observe missing-module failures.
3. Implement `rough_z_tilt.py`, preserving native motor geometry and probe
   execution; implement deterministic preview and configuration validation.
4. Run the suite and inspect the extension with real Klipper 0.12 and 0.13
   helper/solver code without hardware motion. Add an install script, examples,
   public documentation, license and CI. Review the public tree for host data.
5. Preserve Pandora2's original config in local Git. Install the extension and
   a local macro override, parse the config, restart only while idle, and verify
   ready state, registration, preview, original probe points and no motion.
6. Commit verified work and create/push the requested public GitHub repository.
   Physical leveling remains an attended hardware check.
