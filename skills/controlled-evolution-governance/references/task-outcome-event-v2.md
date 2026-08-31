# TaskOutcomeEvent V2

V6 事件只保存生命周期元数据。核心键包括 `event_id/event_type/session_id/turn_id/task_id/project_id/repo_fingerprint/terminal_outcome/actual_model/actual_reasoning_effort`、三个事实来源字段和非负计数。

- `event_id` 必须唯一。
- `project_id` 与 `repo_fingerprint` 必须同时匹配当前项目。
- `terminal_outcome` 只允许 `PASS/BLOCKED/FAILED/CANCELLED/PARTIAL/UNKNOWN`。
- 缺少明确终态时使用 `UNKNOWN`，不把 Stop 自动等同于成功。
- `actual_model_source/actual_reasoning_effort_source/terminal_outcome_source` 只允许 `hook-payload/unavailable`；通用 model、reasoning、status 或配置值不得推断为实际宿主事实。
- 默认禁止保存 Prompt、回答、代码、Diff、认证凭据等正文。
- JSONL 使用前向 SHA-256 链；活动文件达到阈值后在同一锁内形成连续只读分段，跨段链保持连续。活动文件的未提交尾部会进入摘要化隔离文件，历史段损坏失败关闭。
- 配置 `CP_ASSISTANT_HMAC_KEY` 后增加 HMAC 完整性校验。它是完整性检测，不是不可抵赖审计。
