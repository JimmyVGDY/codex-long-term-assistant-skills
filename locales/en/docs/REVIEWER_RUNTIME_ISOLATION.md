# Reviewer Runtime Isolation and Acceptance

## 1. Background

Reviewer TOML may declare:

```toml
sandbox_mode = "read-only"
```

This is intended configuration, not proof that a subagent received an independent read-only sandbox. During Windows Codex acceptance on 2026-07-29, the parent session used `danger-full-access`, and a `cp_review_functional_business` Reviewer successfully ran:

```powershell
Set-Content -Path ".review-sandbox-probe" -Value "probe" -NoNewline
```

The command exited `0` and the file existed. System-level read-only isolation therefore failed in that environment.

## 2. Isolation Levels

| Level | Runtime Condition | May Claim System-Enforced Read-Only |
|---|---|---:|
| Level A: `system-readonly` | Parent session is actually read-only, or a controlled probe is explicitly sandbox-denied | Yes |
| Level B: `logical-readonly` | Parent is writable and Reviewer refrains by instruction, or probe write succeeds | No |
| Level C: `self-review` | Implementation agent reviews its own work without independent Reviewer context | No |
| `unknown` | Evidence is insufficient | No |

Independent reasoning remains useful, but reasoning independence and permission isolation are separate dimensions.

## 3. Recommended Strict Review

For production, real data, authorization security, money, inventory, irreversible migration, or explicit strict read-only requirements, use two sessions:

```text
Session A: writable implementation
Modify -> targeted tests -> stable git diff -> checkpoint
                |
Session B: entirely read-only review
Verify baseline -> start Reviewers -> consolidate -> report
                |
Session A: centralized repair
Resolve blockers -> rerun validation -> targeted rereview
```

When the parent is read-only, inherited subagent permissions preserve an overall read-only boundary.

## 4. Controlled Write Probe

### 4.1 Use

The probe is for runtime-isolation acceptance after installation or upgrade, not every review.

### 4.2 Safety

- Run only in a disposable temporary Git repository.
- Do not access the real project, production directories, real data, account home directories, or credential directories.
- Create only `.review-sandbox-probe`.
- Do not modify `config.toml`, AGENTS, Skills, Reviewer TOML, or environment variables.
- The coordinator removes the disposable directory after completion.

### 4.3 Interpretation

| Result | Interpretation |
|---|---|
| Explicit sandbox denied and no file | System isolation passed |
| File created | System isolation failed; downgrade to logical read-only |
| Command syntax, parameter, shell, or path error | Invalid test |
| Ordinary filesystem permission denied | Proves only that path is unwritable, not necessarily Reviewer sandboxing |

## 5. State Controller

Initialize strict review:

```bash
python3 review_controller.py init \
  --review-dir "/path/reviews/FB-001" \
  --boundary-id "FB-001" \
  --risk-level high \
  --strict-readonly-required
```

Record a system-read-only parent:

```bash
python3 review_controller.py isolation \
  --review-dir "/path/reviews/FB-001" \
  --review-mode independent-agent \
  --parent-sandbox read-only \
  --declared-sandbox read-only \
  --probe-result not-run \
  --agent-config-confirmed \
  --runtime-agent-confirmed \
  --evidence "Parent runtime confirmed read-only"
```

Record a writable parent and successful write probe:

```bash
python3 review_controller.py isolation \
  --review-dir "/path/reviews/FB-001" \
  --review-mode independent-agent \
  --parent-sandbox danger-full-access \
  --declared-sandbox read-only \
  --probe-result write-succeeded \
  --agent-config-confirmed \
  --runtime-agent-confirmed \
  --evidence "Probe created successfully in disposable repository"
```

The second state becomes `logical-readonly`. If strict read-only was required at initialization, later `plan` and `dispatch` are blocked.

## 6. Report Wording

Allowed:

- “Reviewer TOML declares read-only; the parent is danger-full-access, so this round is logically read-only.”
- “The parent session is actually read-only, so this round meets system-isolation review conditions.”
- “No runtime-isolation evidence was obtained; system-level read-only remains unverified.”

Prohibited:

- “TOML says read-only, so the Reviewer cannot write.”
- “The Reviewer changed no files, so system isolation passed.”
- “System-enforced read-only review completed under a writable parent session.”
