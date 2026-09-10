# V7.7.0 发行说明

本次发行恢复明确启用项目的受控 `apply_patch` 写入路径，同时保持普通对话和未启用项目不受门禁状态影响。

- 新增仓库外 Operation v2：首次调用 A 只创建起点并拒绝；准备后必须由不同调用 B 原子领取许可。
- 新增规范 PreToolUse/PostToolUse 适配，仅信任 `tool_name=apply_patch`、`tool_input.command` 与真实 `tool_use_id`；Edit/Write 只作为 matcher 别名。
- `capability-task-prepare/finish/check/cancel` 支持 `--operation-ref`，CLI 不能创建宿主起点或填写 dispatch ID；旧 session/turn 参数继续兼容 GateTask v1。
- 完成验证必须具备匹配 B 的 PostTool 回执、范围内实际变化、完整复用决策、索引维护和仓库外回执读回。策略变化、许可后取消、缺回执或证据失效保持 `OUTCOME_UNKNOWN`。
- 补丁正文不写入 Operation、回执或观察链；Patch 命令、目标数量、路径和文件读取均有固定上限。
- 11 个冻结 Codex 稳定版本分别绑定官方 PreToolUse/PostToolUse schema，以及成功 ApplyPatchToolOutput、PostTool payload 和字符串响应实现的 tag、commit、路径与 SHA-256；缺少任一证据的宿主不安装静态强制 Hook。

Hook 许可与真实文件写入不是跨进程原子事务；shell、MCP 和未知写入口不在本协议覆盖内。流程证据不批准业务语义，也不授予提交、推送、发布、部署或数据写入权限。
