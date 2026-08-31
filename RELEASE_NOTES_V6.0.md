# V6.0 Release Notes — 插件化确定性自观察版

## 发布目标

V6.0 不是扩大“自动自我修改”权限，而是提高 **观察确定性、证据可信度、项目隔离、成本约束和人工治理闭环**。

## 关键变更

1. 账户级 Skill 目录修正为 `$HOME/.agents/skills`；Repo 级仍为 `$REPO_ROOT/.agents/skills`。
2. 新增 Plugin Manifest 与六类 Hooks，并保留 standalone/repo 兼容模式。
3. 新增 `TaskOutcomeEvent V2`，所有计数字段强制非负，默认脱敏，不记录 Prompt/回答/代码/Patch/凭据正文。
4. 自观察先做 Event 去重和 Task 聚合，再做 Project 统计。
5. V2 记录严格校验 `project_id + repo_fingerprint`；Hash Chain/HMAC 失败时停止形成结论。
6. `status=PLAN/RUNNING/...` 不再被当成失败；Reviewer 明细存在时不与汇总计数重复相加。
7. Snapshot ID 引入随机唯一性；`source_digest` 用于同源比较；快照只允许首次创建，禁止同名覆盖。
8. Proposal Assessment 必须匹配 Snapshot、Signal、Target、Policy 和 Evidence；相同 Evidence fingerprint 不机械重生。
9. Proposal 增加 `IMPLEMENTATION_LINKED / VALIDATION_RECORDED / CLOSED / SUPERSEDED` 生命周期。
10. PreToolUse 对显式 Sol、未知更强模型、`xhigh/max/ultra` 采用 fail-closed；SubagentStart 仍记录实际模型。
11. 安装器统一为一个事务实现，Shell/PowerShell 脚本只做包装，避免多套删除/复制逻辑漂移。
12. 新增第 10 个 Skill：`controlled-evolution-governance`，把自观察治理从普通 Review Skill 中拆出，降低误触发。
13. 全局 AGENTS 缩减，详细流程下沉 Skill/Reference，降低常驻上下文成本。

## 不变的安全边界

- `execution_authorization=NONE`
- 不自动修改 Skill / Reviewer / AGENTS / 模型路由 / 业务代码
- 不自动 ACCEPT Proposal
- 不自动 Commit / Push / Deploy / Restart / Production Write
- Evidence 不等于 Approval

## 已验证

- Python 编译
- JSON/TOML 解析
- 19 项本地单元/回归测试
- Plugin/Standalone 安装结构烟测
- Repo/User 目标路径与符号链接防护测试
- Event V2 非负数、去重、跨项目隔离、Hash Chain/HMAC
- `status=PLAN` 误判回归
- Reviewer Finding 双计数回归
- 不可覆盖 Snapshot
- Terra High 模型上限 Hook
- Proposal 实施/验证/关闭状态机
- 35 条路由用例 Schema 校验

## 未伪装成已验证的项目

- 真实 Codex 会话的隐式 Skill 激活率、误触发率、漏触发率
- Windows PowerShell 实机与 Junction 对抗
- 各 Codex 宿主版本 Plugin/Hooks 端到端加载
- 长时间高并发事件写入压测

以上必须在对应真实环境中执行后才能升级为 PASS。
