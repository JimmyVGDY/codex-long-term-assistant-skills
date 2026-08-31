# Codex 跨项目长期技术助手 Skills 安装包 V4.2

V4.2 在 V4.1 的执行确定性和独立上下文基础上，重点优化子 Agent 模型消耗、Reviewer 数量、重复上下文、重复扫描、复审轮次和长期记忆写入频率。9 个 Skill 与 7 个专业 Reviewer 保持不变。

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

## V4.2 核心增强

1. 自动子 Agent 四级路由：`luna-low -> luna-medium -> terra-medium -> terra-high`；
2. 自动流程最高为 Terra High，禁止自动使用 Sol、`xhigh`、`max` 和 `ultra`；
3. 主 Agent 模型保持用户选择，辅助 Skill 和 Reviewer 不机械继承主 Agent 的高强度；
4. 默认复审预算收敛为并行 3、累计 6、post 2 轮、集中修复 2 轮、Terra High 1 个；
5. 审查包增加摘要、diff stat、name status、推荐读取顺序和 freshness 检查；
6. 相同 Reviewer/相同 packet、零发现相同 packet 和无新信息轮次受到重复派发保护；
7. Reviewer 渐进读取、唯一职责、根因合并和结构化模型运行证据；
8. 长期记忆采用事件驱动、连续 8 个实质动作兜底、最近 3 个检查点恢复、20 条热区和内容去重；
9. 全局 `AGENTS.md` 大幅压缩，领域规则继续按需加载；
10. 新增 Codex `config.toml` 分步配置指南和 V4.2 语义/回归校验。

## 安装

可从 V4.1、V4.0 或更早版本原地升级。建议先 dry-run，再正式安装。

### Windows PowerShell

```powershell
powershell -ExecutionPolicy Bypass -File ".\scripts\install-user.ps1" -DryRun
powershell -ExecutionPolicy Bypass -File ".\scripts\install-user.ps1"
powershell -ExecutionPolicy Bypass -File ".\scripts\verify-user-install.ps1"
powershell -ExecutionPolicy Bypass -File ".\scripts\doctor.ps1"
```

### WSL / Linux / macOS

```bash
./scripts/install-user.sh all --dry-run
./scripts/install-user.sh all
./scripts/verify-user-install.sh
./scripts/doctor.sh
```

安装脚本会备份同名受管资源，但**不会自动修改用户的 `config.toml`**。安装后按 `docs/CODEX_CONFIG_GUIDE.md` 合并 `[agents]` 配置。

恢复最近一次安装前状态：

```powershell
powershell -ExecutionPolicy Bypass -File ".\scripts\restore-latest-backup.ps1"
```

```bash
./scripts/restore-latest-backup.sh
```

## 验证

```bash
python3 scripts/validate-package.py
python3 scripts/semantic-lint.py
```

## 重要边界

- `[agents]` 中的 Luna/Medium 是未显式指定时的默认值，不是 Codex 平台级 allowlist；
- V4.2 通过全局规则、Skill 和 `review_controller.py` 约束并审计本工作流，无法从底层阻止用户手工绕过控制器；
- Reviewer TOML 有意不写死模型和推理强度，以保留动态路由；
- 独立上下文不等于系统只读，严格任务仍需验证父会话和运行时隔离；
- 降低 Reviewer 数量不能降低证据标准，证据不足必须记录为未验证或按规则升级。

详见：

- `docs/CODEX_CONFIG_GUIDE.md`
- `docs/MODEL_ROUTING_AND_COST_POLICY.md`
- `docs/V4_2_COST_FLOW_OPTIMIZATION.md`
- `docs/SUBAGENT_INDEPENDENT_CONTEXT.md`
- `docs/VALIDATION_REPORT.md`
