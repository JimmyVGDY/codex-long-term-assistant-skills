<!-- Generated from locales/en/docs/releases/v7.6.2/RELEASE_NOTES.md; edit that source and run scripts/documentation.py sync. -->

# V7.6.2 Release Notes

This patch fixes non-blocking Hook behavior and isolates legacy optional capability-gate state.

- Register UserPromptSubmit as asynchronous only when the compatibility evidence confirms that capability; optional feedback no longer blocks ordinary prompts.
- Bind each of the 11 frozen Codex versions to an official source tag, commit, path, and SHA-256; the Plugin's static async registration is written only after host preflight succeeds, while unknown versions fail closed.
- Native writes fail closed with an enabled legacy policy, while unconfigured or disabled policies remain neutral.
- UserPromptSubmit and Stop do not read or mutate legacy GateTask state.

This record covers only completed implementation and focused tests. It does not imply full release validation, independent review, commit, push, public publication, account installation, or effective-state readback.
