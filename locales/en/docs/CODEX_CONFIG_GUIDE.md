# Codex Configuration Guide

## Scope

V7.1 does not override the main-agent model. Reviewer TOML files omit model settings so the bounded coordinator policy can select Luna or Terra profiles dynamically.

## Windows path normalization

For native Windows Codex, `CODEX_HOME` must resolve to a native Windows path. WSL-style drive mappings are normalized before use. A literal `/mnt/c/...` path is not an installation destination for a native Windows process.

## Plugin registration

The installer uses Codex 0.152.1 Plugin and Marketplace commands. Registration is verified through:

```powershell
codex plugin list --json
```

Files present on disk do not establish Plugin installation or enablement.

## Hook configuration

The Plugin supplies six Hooks through `hooks/hooks.json`. Windows commands invoke `hooks\cp_hook.cmd`, which selects an available Python launcher without any extra `python3.exe` shim.

SessionEnd keeps the host timeout at three seconds. It performs bounded signed enqueue work and launches delayed sealing outside the Hook budget.

## Automatic model ceiling

Allowed automatic profiles:

```text
gpt-5.6-luna / low
gpt-5.6-luna / medium
gpt-5.6-terra / medium
gpt-5.6-terra / high
```

Explicit Sol, `xhigh`, `max`, `ultra`, and unknown models fail closed. Host defaults remain allowed only when no explicit automatic model is requested; actual runtime evidence still depends on trusted host attestation.
