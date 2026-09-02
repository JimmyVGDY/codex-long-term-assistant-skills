# Codex Configuration Guide

Chinese: [`CODEX_CONFIG_GUIDE.md`](CODEX_CONFIG_GUIDE.md)

## Scope

V7.1 does not override the main-agent model. Reviewer TOML files omit model settings so the bounded coordinator policy can select Luna or Terra profiles dynamically.

## Windows path normalization

For native Windows Codex, `CODEX_HOME` must resolve to a native Windows path. WSL-style drive mappings are normalized before use and are never used literally as native installation paths.

## Plugin registration

The installer uses Codex 0.152.1 Plugin and Marketplace commands. Registration is verified through `codex plugin list --json`; files present on disk do not establish installation or enablement.

## Hook configuration

The Plugin supplies six Hooks through `hooks/hooks.json`. Windows commands invoke `hooks\cp_hook.cmd`, which selects an available Python launcher without an extra `python3.exe` shim.

SessionEnd keeps the host timeout at three seconds. It performs bounded signed enqueue work and launches delayed sealing outside the Hook budget.

## Automatic model ceiling

Allowed automatic profiles are Luna Low, Luna Medium, Terra Medium, and Terra High. Explicit Sol, `xhigh`, `max`, `ultra`, and unknown models fail closed. Actual runtime evidence still depends on trusted host attestation.
