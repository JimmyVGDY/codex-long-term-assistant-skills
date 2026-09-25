# V7.13.4 Validation Record

- Focused permissions, name normalization, full-name matching, and migration regressions passed; original failing controls remain recorded.
- The final behavioral baseline passed 779 package tests and 231 runtime tests; report digests are in `PACKAGE_VALIDATION.json`. Later scope-wording corrections require separate projection, link, and package-integrity checks.
- The actual local Desktop component was `0.155.0-alpha.16.4`. Installation, verify/doctor, ordinary-sandbox reads with writes denied, and fresh-process Plugin loading passed separately.
- Native V4 reentry rejection passed. Positive creation was denied before execution because opaque encrypted message input does not match the approved plaintext digest, with reason `V4_REQUEST_MESSAGE_MISMATCH`; positive admission is not claimed.
- The observed native input exposed no decoded-input metadata. The documented input-rewrite mechanism caused a decoding error in this encrypted self-message experiment. No child was created, and temporary Hooks/trust entries were restored.
- Official stable-component artifacts/source digests and internal multi-version contract samples prove only their own checks; they do not replace actual Desktop acceptance.
- CI, tag, assets, provenance, public downloads, and site readback remain separate gates. No completion claim precedes readback.
