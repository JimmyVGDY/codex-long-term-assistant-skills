# Evidence Fingerprint 与 Freshness 协议

## 目标

防止代码、配置或 Git 差异在测试、复审或审批后继续变化，但 Agent 仍沿用旧的“已通过”结论。

## 指纹组成

- Git HEAD、分支和 Remote；
- 暂存与未暂存差异；
- 有界未跟踪文件路径与内容摘要；
- 当前功能边界的相关文件；
- 执行命令、环境、退出码和结果文件；
- Reviewer 审查包 hash；
- Project ID、Task ID 和记录时间。

## 状态

- `current`：当前仓库指纹与记录一致；
- `stale`：代码、配置、差异或绑定变化，旧 Evidence 不能继续证明当前版本；
- `failed`：命令实际失败；
- `blocked`：环境或权限不足；
- `unknown`：证据不完整。

## 强制规则

1. 验证和复审 Evidence 必须绑定当前项目、任务和仓库指纹。
2. 任何受影响代码、公共契约、迁移或配置变化后，相关 Evidence 自动视为 `stale`。
3. 复审后修复代码时，旧 Review Packet 和受影响测试不能继续标记为有效。
4. 全量测试中的历史失败必须单独保留，不能因为指纹一致就忽略。
5. Evidence 只证明动作和结果，不授予 Commit、Push、Deploy、Restart、数据写入或生产权限。
6. `execution_guard.py validate` 和 `cp-runtime.py evidence-check` 只判断证据与当前状态是否一致，不替代测试本身。
