<!-- Generated from locales/en/docs/releases/v7.11.2/VALIDATION_REPORT.md; edit that source and run scripts/documentation.py sync. -->

# V7.11.2 Validation Report

## Verified

- The official OpenAI changelog and npm `latest` both identify Codex CLI 0.155.1; GitHub `rust-v0.155.1` is a non-prerelease stable release.
- npm integrity and tarball SHA-256 are frozen; the official tag commit is `be2951ea34f0d295ed0becf97079f92fa5f6950e`.
- Hook discovery, Hook schema, and apply_patch result source-contract digests are unchanged from 0.155.0.
- Windows 0.155.1 version output, Plugin/Marketplace command help, empty Plugin list, isolated Plugin preflight, and synthetic Hook contracts pass.
- The closed current-plus-ten stable window is registered and 0.150.1 has left the active window.

## Independent gates

Full package tests, runtime tests, bilingual and reproducible builds, independent review, account installation, fresh-process acceptance, main CI, stable compatibility matrix, and tag release workflow are executed and read back separately during delivery. Local validation does not substitute for remote publication state.

The candidate records `RELEASE_COMPLETE=false` and `INCIDENT_EFFECTIVE=UNVERIFIED`. They must be updated independently; publication completion does not prove that an already-open task or another incident state has taken effect.
