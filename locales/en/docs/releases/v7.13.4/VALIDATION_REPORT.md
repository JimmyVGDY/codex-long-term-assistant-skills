# V7.13.4 Validation Record

- npm `latest` and GitHub `rust-v0.157.0` identify a non-prerelease stable release.
- Official artifact integrity, SHA-256, tag commit, and Hook/apply_patch source hashes are frozen in the registry.
- The window contains exactly 0.157.0 through 0.153.0; 0.152.1 fails closed.
- Package, runtime, isolated Plugin, synthetic Hook, account, fresh-process, CI, tag, asset, provenance, and public-download gates are recorded separately.
- Actual Desktop installation, verify/doctor, ordinary-sandbox payload read with write denial, and fresh-process Plugin loading pass.
- Native V4 reentry denial passes. A positive native spawn is denied before charge/creation with `V4_REQUEST_MESSAGE_MISMATCH` because the Desktop message field is an opaque encrypted transport value. No body-validation weakening, receipt synthesis, or positive-admission claim is made.

No remote or public state is claimed before readback.
