# V7.4 Codex Configuration Guide

> Status: `active`. This page covers current V7.4 configuration only. Follow [installation and recovery](INSTALLATION_RECOVERY.en.md) for installation, upgrade, and recovery procedures.

## 1. Configuration boundaries

- The main Agent continues to use the model selected by the user in Codex; this package does not override it.
- Sub-agents without an explicit model may use the host default.
- Automatic dispatch by this package permits only Luna Low, Luna Medium, Terra Medium, and Terra High.
- Reviewer TOML files do not hard-code a model or reasoning effort; bounded scheduling selects them per task.
- Exact model configuration is used only transiently by the host dispatch adapter for request validation and never enters package state or governance conclusions.

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

V7.4.3 uses a frozen registry for the Plugin and Marketplace interfaces in Codex CLI 0.153.2 and the ten preceding stable releases. Plugin registration is established only when `codex plugin list --json` reads back `installed=true`, `enabled=true`, and `version=7.4.3`, and the schema-3 host snapshot is `HOST_COMPATIBLE`. Files present on disk do not establish installation or enablement.

The Plugin supplies six Hooks through `hooks/hooks.json`. On Windows, `hooks\cp_hook.cmd` selects an available Python launcher without an extra `python3.exe` shim. SessionEnd keeps a three-second host budget: the Hook only constructs a capped, body-free sanitized Event V3 and dispatches a detached worker without waiting, using a command argument instead of a synchronous pipe. It neither scans nor writes the event chain. Outside the Hook budget, the worker validates stable lifecycle identity, semantically deduplicates, persists the terminal event, creates the signed job, and seals the chain. Every queue entry point rejects missing stable lifecycle IDs, and an unsealed `seal_required` chain cannot enter Evolution.

## 7. Automatic model ceiling

```text
gpt-5.6-luna / low
gpt-5.6-luna / medium
gpt-5.6-terra / medium
gpt-5.6-terra / high
```

Automatic flows fail closed for explicit Sol, `xhigh`, `max`, `ultra`, unknown models, and every configuration above Terra High. An omitted automatic model uses the Task Envelope default approved profile for accounting; after dispatch the package never reads or infers host runtime model information.

## 8. Reload and verify

After changing the configuration or Reviewer files, fully close and reopen the Codex App, CLI session, or IDE extension. Then verify:

1. `/model` still shows the user's selected main model.
2. `codex plugin list --json` reads back the target Plugin's installation, enabled state, and version.
3. A new task can discover ten V7.4 Skills and seven Reviewers.
4. A small read-only review does not start many Reviewers without justification.
5. Review results contain only the approved dispatch profile, permit reference, reserved units, outcome metrics, and isolation level.

See [installation and recovery](INSTALLATION_RECOVERY.en.md) for the complete `doctor`, dry-run, verify, and recovery workflow.
