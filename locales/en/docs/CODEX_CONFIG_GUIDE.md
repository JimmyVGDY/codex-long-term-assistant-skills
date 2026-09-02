# V7.3 Codex Configuration Guide

> Status: `active`. This page covers current V7.3 configuration only. Follow [installation and recovery](INSTALLATION_RECOVERY.md) for installation, upgrade, and recovery procedures.

## 1. Configuration boundaries

- The main Agent continues to use the model selected by the user in Codex; this package does not override it.
- Sub-agents without an explicit model may use the host default.
- Automatic dispatch by this package permits only Luna Low, Luna Medium, Terra Medium, and Terra High.
- Reviewer TOML files do not hard-code a model or reasoning effort; bounded scheduling selects them per task.
- Configuration expresses request intent. Trusted host evidence is still required to establish the actual runtime model.

## 2. Configuration file location

### Windows PowerShell

```powershell
$env:USERPROFILE + "\.codex\config.toml"
```

### WSL, Linux, and macOS

```bash
${CODEX_HOME:-$HOME/.codex}/config.toml
```

Windows and WSL can use different account directories. For native Windows Codex, `CODEX_HOME` must resolve to a native Windows path; a literal `/mnt/c/...` value is not a native installation destination.

## 3. Back up before editing

PowerShell:

```powershell
$path = "$env:USERPROFILE\.codex\config.toml"
Copy-Item -LiteralPath $path -Destination "$path.bak-$(Get-Date -Format yyyyMMdd-HHmmss)" -ErrorAction SilentlyContinue
```

Bash:

```bash
path="${CODEX_HOME:-$HOME/.codex}/config.toml"
[ -f "$path" ] && cp "$path" "$path.bak-$(date +%Y%m%d-%H%M%S)"
```

## 4. Sub-agent defaults

Keep only one `[agents]` table in the configuration file. Merge fields into an existing table instead of appending a duplicate.

```toml
[agents]
enabled = true
max_concurrent_threads_per_session = 3
default_subagent_model = "gpt-5.6-luna"
default_subagent_reasoning_effort = "medium"
```

These are host defaults and do not prevent explicit dispatch from selecting another allowed tier. Do not disable interruption messages merely to save a small amount of context; the host default is more useful for recovery and auditability.

## 5. Reviewer configuration

Managed Reviewer files should retain dynamic model selection:

```text
${CODEX_HOME:-$HOME/.codex}/agents/cp-review-*.toml
```

Do not add a fixed setting to every file:

```toml
model = "gpt-5.6-terra"
model_reasoning_effort = "high"
```

A hard-coded model overrides bounded scheduling and `[agents]` defaults, breaking the progressive Luna-to-Terra-High route.

## 6. Plugin and Hooks

V7.3 uses the Plugin and Marketplace interfaces in Codex CLI 0.152.1. Plugin registration is established only when `codex plugin list --json` reads back `installed=true`, `enabled=true`, and `version=7.3.0`. Files present on disk do not establish installation or enablement.

The Plugin supplies six Hooks through `hooks/hooks.json`. On Windows, `hooks\cp_hook.cmd` selects an available Python launcher without an extra `python3.exe` shim. SessionEnd keeps a three-second host budget, performs only bounded signed enqueue work, and launches delayed sealing outside the Hook budget.

## 7. Automatic model ceiling

```text
gpt-5.6-luna / low
gpt-5.6-luna / medium
gpt-5.6-terra / medium
gpt-5.6-terra / high
```

Automatic flows fail closed for explicit Sol, `xhigh`, `max`, `ultra`, unknown models, and every configuration above Terra High. Host defaults remain permitted when no automatic model is explicitly requested, but request values and diagnostic fields are not proof of the actual runtime model.

## 8. Reload and verify

After changing the configuration or Reviewer files, fully close and reopen the Codex App, CLI session, or IDE extension. Then verify:

1. `/model` still shows the user's selected main model.
2. `codex plugin list --json` reads back the target Plugin's installation, enabled state, and version.
3. A new task can discover ten V7.3 Skills and seven Reviewers.
4. A small read-only review does not start many Reviewers without justification.
5. Review results keep requested model, actual-model evidence, and isolation level separate.

See [installation and recovery](INSTALLATION_RECOVERY.md) for the complete `doctor`, dry-run, verify, and recovery workflow.
