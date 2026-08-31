# Codex 跨项目长期技术助手 Skills 安装包 V5.0

V5.0 在 V4.2 的 9 个 Skill、7 个专业 Reviewer、Luna/Terra 模型分级、审查包、证据指纹和长期任务检查点基础上，增加轻量项目治理与证据闭环。重点不是把 AICTO 的完整治理体系搬入本包，而是补齐跨项目最容易出错的四个边界：项目身份、授权与证据、任务记忆晋升、最终交付读回。

## 保持不变

- 9 个 Skills 与 7 个 Reviewer 保持不变；
- 主 Agent 仍使用用户当前选择的模型；
- 自动子 Agent 仍只在 `luna-low -> luna-medium -> terra-medium -> terra-high` 范围内逐级路由；
- 默认并行 Reviewer 3 个、累计 6 个、Terra High 1 个；
- Skill 和 Reference 继续按需加载，不建立第二套重型项目生命周期。

## V5.0 核心增强

1. `PROJECT_PROFILE`：稳定保存项目身份、仓库、技术栈、入口、边界与未知项；
2. `PROJECT_STATE`：保存项目阶段、当前基线、风险、阻塞和唯一下一步；
3. 已有项目采用有界只读 Onboarding，不访问网络、不触碰生产；
4. Task Envelope V2 同时记录复杂度、项目阶段、执行档位、Reviewer 预算、模型档位和 Host Surface；
5. Approval 与 Evidence 分离，受保护动作绑定项目、任务、环境、仓库基线和有效期；
6. 代码变化后旧验证与复审证据自动失效；
7. Task Checkpoint、Project Memory、Knowledge Candidate 分为三层，禁止自动晋升；
8. Finalization Integrity 从真实仓库、证据和动作读回状态，阻止把“已修改”误报为“已部署/已生效”；
9. 新增统一标准库运行时 `runtime/cp_runtime`，安装到 Codex Home 后由各 Skill 共用；
10. 安装器增加源码目录保护、受管目标白名单、备份完整性和恢复路径边界检查。

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

## 安装

建议先执行 dry-run，再正式安装。安装会备份同名受管资源，但不会自动修改 `config.toml`，也不会删除已有项目上下文。

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

恢复最近一次安装前状态：

```powershell
powershell -ExecutionPolicy Bypass -File ".\scripts\restore-latest-backup.ps1"
```

```bash
./scripts/restore-latest-backup.sh
```

## 首次接管项目

在安装包目录内可直接运行：

```bash
python3 scripts/cp-runtime.py project-onboard \
  --repo-path /path/to/repo \
  --project-id my-project
```

安装后入口为：

```bash
python3 "$CODEX_HOME/tools/cp-runtime.py" project-show \
  --profile "$CODEX_HOME/project-context/my-project/project-profile.json"
```

默认项目上下文位于：

```text
${CODEX_HOME:-$HOME/.codex}/project-context/<project-id>/
├── project-profile.json
├── project-state.json
├── project-memory.md
├── memory-projections.jsonl
├── knowledge-candidates.jsonl
├── evidence-ledger.jsonl
└── execution-feedback.jsonl
```

## 绑定任务执行状态

```bash
python3 skills/engineering-quality-delivery/scripts/execution_guard.py init \
  --state-dir /external/task-state/TASK-001 \
  --task-id TASK-001 \
  --repo-path /path/to/repo \
  --project-profile "$CODEX_HOME/project-context/my-project/project-profile.json" \
  --complexity L2 \
  --profile STANDARD \
  --reviewer-budget balanced \
  --model-profile terra-medium \
  --host-surface direct-workspace \
  --environment local
```

## Approval、Evidence 与最终读回

- `approval-issue` 只能在用户已经明确授权后记录授权；该命令本身不会替用户作出授权决定；
- `authorize-action` 在动作前核对并消费 Approval；
- `record-action` 只记录动作后的实际读回结果，不执行 Commit、Push、部署或重启；
- `finalize` 检查最终声明是否有当前证据支持。

详细流程见：

- `docs/V5.0_升级说明与迁移指南.md`
- `docs/V5_0_PROJECT_GOVERNANCE_AND_EVIDENCE_CLOSURE.md`
- `docs/PROJECT_CONTEXT_AND_ONBOARDING.md`
- `docs/APPROVAL_EVIDENCE_FINALIZATION.md`
- `docs/AUTHORITY_REGISTRY.md`

## 验证

```bash
python3 scripts/validate-package.py
python3 scripts/semantic-lint.py
```

## 重要边界

- V5.0 的 Approval 是工作流级记录，不是 Codex 平台、操作系统或云平台权限隔离；
- Evidence 不能替代授权，检查器通过也不能替代真实测试、Review、Release Gate 或用户验收；
- Onboarding 只做有界只读识别，推断入口必须保留 `inferred-unconfirmed`；
- 本地 upstream 引用等于 HEAD 不能证明已联网读取远端平台；
- Project Memory 只接收经过审核的 Projection，Knowledge Candidate 默认永远不是 Active；
- 生产、真实数据、不可逆迁移和外部发送仍需单独明确授权、停止条件和回滚方案。
