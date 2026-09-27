<!-- Generated from locales/en/docs/releases/v7.13.6/RELEASE_NOTES.md; edit that source and run scripts/documentation.py sync. -->

# V7.13.6 Release Notes

V7.13.6 fixes a missed budget gate in the Codex Desktop V1 delegation interface. The host canonicalizes V1 creation to `spawn_agent`, while messaging and resume retain `multi_agent_v1send_input` and `multi_agent_v1resume_agent`. Both requests now reach the existing PreToolUse budget gate.

- Register only the two exact names without adding wildcard Hooks; unbound tasks retain neutral behavior.
- Preserve existing creation handling, PostToolUse receipts, message-digest and independent-context checks, and historical ledgers.
- A real local Desktop V1 reentry control was denied. One GPT-6 Luna / Low dispatch produced a reservation, a native creation receipt, a completion record, and one attempt/unit charge.
- The transport probe returned UNKNOWN / ADMISSION_ONLY and is not a quality evaluation. Frozen V3, GPT-5.6 compatibility, and GPT-6 scenario qualification remain unchanged; other Desktop interfaces require their own acceptance.

The product supports Codex Desktop only. Commit, CI, artifacts, publication, installation, and effective behavior are verified separately.
