# Codex 跨项目长期技术助手 Skills 安装包 V4.1

V4.1 在 V4.0 通用前端工程基础上，重点提升 Agent 的执行确定性、独立上下文委派、证据有效性、安装诊断和 Token 控制，不增加 Skill 数量。

## 9 个 Skills

- `$java-backend-engineering`
- `$python-backend-ai-engineering`
- `$frontend-engineering`
- `$data-middleware-ai-infrastructure`
- `$log-observability-analysis`
- `$engineering-quality-delivery`
- `$multi-agent-independent-review`
- `$technical-document-writing`
- `$long-running-task-memory`

## V4.1 核心增强

1. 所有大型 Reference 分片，按任务渐进加载；
2. `LIGHT / STANDARD / STRICT` 执行档位；
3. `IDENTIFY → PLAN → IMPLEMENT → VALIDATE → REVIEW → DELIVER` 阶段状态机；
4. 任务执行信封和 `execution_guard.py`；
5. 验证/复审证据绑定 Git 与差异指纹，代码变化后自动 `stale`；
6. 子 Agent 使用独立上下文，主 Agent 只传最小任务包并接收结构化摘要；
7. `review_packet.py` 统一 Reviewer 基线，`review_controller.py` 管理预算、隔离、packet hash 和成本档位；
8. Reviewer `economy / balanced / deep` 三档；
9. 安装支持 dry-run、doctor、备份与一键恢复；
10. 语义校验检查版本、Skill 引用、旧名称、路径和隔离逻辑。

## 安装

可从 V4.0 或更早的本包版本原地升级，无需先卸载。建议先执行 dry-run，确认目标目录、备份位置、旧 Skill 清理和潜在冲突后再正式安装。

Codex 用户级 Skills 默认安装到 `${CODEX_HOME:-$HOME/.codex}/skills`；doctor 会检查旧 `$HOME/.agents/skills` 中的本包重复副本。

### Windows

```powershell
powershell -ExecutionPolicy Bypass -File ".\scripts\install-user.ps1" -DryRun
powershell -ExecutionPolicy Bypass -File ".\scripts\install-user.ps1"
powershell -ExecutionPolicy Bypass -File ".\scripts\verify-user-install.ps1"
powershell -ExecutionPolicy Bypass -File ".\scripts\doctor.ps1"
```

### WSL / Linux

```bash
./scripts/install-user.sh all --dry-run
./scripts/install-user.sh all
./scripts/verify-user-install.sh
./scripts/doctor.sh
```

安装脚本会备份同名受管资源。需要恢复最近一次安装前状态：

```powershell
powershell -ExecutionPolicy Bypass -File ".\scripts\restore-latest-backup.ps1"
```

```bash
./scripts/restore-latest-backup.sh
```

## 运行验证

安装后重启客户端并检查 Skills。结构和语义校验：

```bash
python3 scripts/validate-package.py
python3 scripts/semantic-lint.py
```

## 重要边界

- 子 Agent 独立上下文用于隔离探索噪声，但不等于权限隔离；
- Reviewer 使用统一审查包，不复制整个主会话；
- 低风险任务使用 LIGHT，不机械多开 Agent；
- 生产、真实数据、不可逆迁移和权限安全任务使用 STRICT；
- 验证或复审后代码变化，旧证据必须重新执行或标记失效。

详见 `docs/V4_1_EXECUTION_ARCHITECTURE.md`、`docs/SUBAGENT_INDEPENDENT_CONTEXT.md`、`docs/DESIGN_REFERENCES.md` 和 `docs/VALIDATION_REPORT.md`。
