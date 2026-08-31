# V5.0 安装包验证报告

## 1. 验证对象

- 平台：Codex
- 版本：`5.0.0`
- 版本名称：项目治理与证据闭环版
- 验证日期：2026-08-26
- 环境：Linux x86_64、Python 3.13.5、Bash 5.2.37、Git 2.47.3
- 环境限制：当前容器未安装 Windows PowerShell，未连接真实 Codex App、CLI 或 IDE 运行时

## 2. 结构与发布完整性

验证内容：

- 保留 9 个 Skill 与 7 个专业 Reviewer；
- 每个 Skill 均包含 `SKILL.md` 与 Codex `agents/openai.yaml`；
- `manifest.json` 版本、Skill、Reviewer、治理运行时和安装目标一致；
- `runtime/cp_runtime` 是包内唯一的项目治理权威实现；
- V5.0 必需合同、CLI、文档、模板和测试均存在；
- Markdown 代码块闭合，所有 Python 文件可编译；
- 包内不存在符号链接、路径穿越条目、Python 缓存和已知密钥格式；
- `CHECKSUMS.sha256` 覆盖除自身以外的全部发布文件，并逐项校验内容哈希。

## 3. V5.0 项目治理与证据闭环

已验证：

- `PROJECT_PROFILE` 与 `PROJECT_STATE` 的创建、完整性密封和 Project ID 绑定；
- 已有项目 Onboarding 只读取 Git 和有限构建标记，不访问网络或生产环境；
- 强制刷新 Profile 时保留已审核的 `project-memory.md`；
- 仓库路径、Remote、Project ID、Profile Hash 或 State 绑定不一致时失败关闭；
- Task Envelope V2 保留 `LIGHT / STANDARD / STRICT`，并增加复杂度、项目阶段、Reviewer 预算、模型档位、Host Surface 和环境；
- 仓库指纹覆盖 HEAD、工作区、暂存区以及未跟踪文件路径与内容摘要。

## 4. Approval、Evidence 与 Finalization

已验证：

- Approval 绑定 Project、Task、操作、环境、仓库基线、有效期和一次性消费状态；
- 非受保护操作、已过期授权、跨项目、跨任务、跨环境、基线变化和重复消费均被拒绝；
- Approval、Evidence、Finalization 产物默认必须位于业务仓库之外；
- Evidence 只记录观察结果，不授予 Commit、Push、Deploy、Restart 或数据写入权限；
- 工作区、暂存区或未跟踪内容变化后，旧 Evidence 自动判定为 `STALE`；
- Finalization 读取真实仓库和动作记录，分别判断 Modified、Validated、Reviewed、Committed、Pushed、Deployed、Restarted 与 Effective；
- 没有对应读回证据时，外部动作声明返回阻断结果。

## 5. 记忆分层与受控晋升

已验证：

- Task Checkpoint、Project Memory Projection、Project Memory 和 Knowledge Candidate 分层；
- Projection 未审核前不能进入 Project Memory；
- 未晋升 Projection 不能创建跨项目 Knowledge Candidate；
- 晋升操作绑定 Project Profile，并保留审核人和审核时间；
- Knowledge Candidate 默认处于 `CANDIDATE` 且不可自动激活；
- 长期任务检查点继续支持内容指纹去重、最近 3 个检查点恢复、20 条热区上限和 8 个实质动作兜底。

## 6. Reviewer、模型与成本控制回归

已验证：

- 复审默认并行最多 3 个、单边界累计最多 6 个、Terra High 最多 1 个；
- Luna Low、Luna Medium、Terra Medium、Terra High 四级路由仍然有效；
- Reviewer TOML 不写死模型，模型请求、实际模型、回退和不匹配状态继续进入审查台账；
- 相同 Reviewer 与相同 Review Packet 的机械重复派发被拦截；
- Review Packet 继续包含摘要、diff stat、name-status、完整差异和 freshness 信息；
- 父会话可写时不得把逻辑只读 Reviewer 声称为系统级只读隔离。

## 7. 自动化测试结果

以下 7 个测试入口全部通过：

```text
runtime/tests/test_cp_runtime.py                                  6 tests
skills/frontend-engineering/tests/test_detect_frontend_stack.py 12 tests
skills/engineering-quality-delivery/tests/test_execution_guard.py
skills/engineering-quality-delivery/tests/test_execution_guard_v5.py 3 tests
skills/multi-agent-independent-review/tests/test_review_tools.py
skills/long-running-task-memory/tests/test_checkpoint_dedupe.py
tests/test_package_manager_security.py                            2 tests
```

同时通过：

```text
scripts/semantic-lint.py
scripts/routing-eval.py validate（35 条路由用例）
```

## 8. 隔离安装、诊断与恢复

在临时 `HOME` 和 `CODEX_HOME` 中执行并通过：

```text
package_manager.py install --dry-run
package_manager.py install
package_manager.py verify
package_manager.py install（幂等重复安装）
package_manager.py verify（重复安装后）
package_manager.py doctor
package_manager.py restore
install-user.sh all --dry-run
install-user.sh all
verify-user-install.sh
doctor.sh
restore-latest-backup.sh
bash -n scripts/*.sh
```

验证期间未修改当前用户的 Codex 目录；校验前后发布源码树哈希保持一致。

## 9. 明确未验证项

- Windows PowerShell 5.1 与 PowerShell 7 的实机包装脚本；
- 真实 Codex 运行时中的隐式 Skill 路由、自定义 Agent 发现、并行调度和模型回退；
- 真实 Token、缓存和 credits 数据；
- Codex 平台对模型上限与沙箱权限的强制执行能力；
- 真实 Git 托管平台的 Push、真实部署、重启、生产数据写入和业务生效；
- 操作系统、云平台和生产发布系统的权限隔离。本包的 Approval 仅为工作流级约束。

## 10. 结论

V5.0 的包结构、项目绑定、Approval/Evidence 分离、Finalization 读回、记忆晋升、原有模型与 Reviewer 策略、路由回归、隔离安装、诊断、恢复和发布树稳定性均已在当前 Linux 环境中通过。Windows 与真实 Codex/生产运行时行为仍应在目标环境中执行本机验收。
