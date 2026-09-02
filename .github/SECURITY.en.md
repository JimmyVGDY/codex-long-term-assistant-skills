# Security policy

Chinese version: [SECURITY.md](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/blob/main/.github/SECURITY.md)

## Supported versions

| Version | Status |
| --- | --- |
| 7.2.0 | Currently maintained |
| 7.1.0 and earlier | Historical evidence only; upgrade preferred |

## Reporting a vulnerability

Submit security findings privately through the repository's [Private vulnerability reporting](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/security/advisories/new). Public Issues, Pull Requests, discussions, and commits are not suitable for vulnerability details, credentials, tokens, cookies, private paths, or other sensitive information.

A useful report includes:

- affected version and platform;
- minimal reproduction steps;
- impact and necessary attack conditions;
- attempted mitigations;
- redacted logs or evidence.

After receipt, maintainers will confirm scope and reproduction conditions before coordinating remediation, validation, and disclosure. Keep details private until the remediation is public.

## Credentials and privacy

- Never commit real tokens, cookies, API keys, passwords, private keys, or environment files.
- Redact screenshots, logs, and event samples before sharing.
- Hooks retain minimal structured metadata by default, not raw prompts, complete responses, source bodies, or diffs.
- Rotate suspected credentials at their provider immediately. Removing text from Git history is not a substitute for rotation.

This policy does not promise a fixed response time. Reports are prioritized by impact and exploitability.
