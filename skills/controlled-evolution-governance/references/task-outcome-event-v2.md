# TaskOutcomeEvent V2

V6 事件只保存生命周期元数据。核心键包括 `event_id/event_type/session_id/turn_id/task_id/project_id/repo_fingerprint/terminal_outcome/actual_model/actual_reasoning_effort`、三个事实来源字段和非负计数。

- `event_id` 必须唯一。
- `project_id` 与 `repo_fingerprint` 必须同时匹配当前项目。
- `terminal_outcome` 只允许 `PASS/BLOCKED/FAILED/CANCELLED/PARTIAL/UNKNOWN`。
- 缺少明确终态时使用 `UNKNOWN`，不把 Stop 自动等同于成功。
- `actual_model_source/actual_reasoning_effort_source/terminal_outcome_source` 只允许受控来源枚举；模型字段只有 `host-attested-hook-payload` 可作为 V6.6 runtime VERIFIED，旧 `hook-payload` 保留为历史兼容，通用 model、reasoning、status 或配置值不得推断为实际宿主事实。
- 默认禁止保存 Prompt、回答、代码、Diff、认证凭据等正文。
- JSONL 使用前向 SHA-256 链；活动文件达到阈值后在同一锁内形成连续只读分段，跨段链保持连续。活动文件的未提交尾部会进入摘要化隔离文件，历史段损坏失败关闭。
- 配置 `CP_ASSISTANT_HMAC_KEY` 后增加 HMAC 完整性校验。它是完整性检测，不是不可抵赖审计。

## V6.5 完整性封印

- 原始 TaskOutcomeEvent schema 保持 2.0；
- keyring HMAC 写入独立 detached seal，不改变事件 envelope；
- `SEALED_CURRENT` 表示当前链头已封印；合法新事件会形成未封印尾部；
- V6.4 写入与 V6.5 封印可并存，历史封印不会因新尾部失效；
- Windows DPAPI keyring 与 POSIX keyring 按 issuer 隔离，不静默跨后端使用。

## Reviewer 校准输入

`reviewer_results` 以 `(task_id, reviewer, result_id)` 去重。相同身份重放只计一次，payload 冲突进入 `CONFLICT`，缺少稳定身份的记录不进入校准样本。校准状态只形成观察或 Proposal 候选，不授予执行权限。

## V6.6 延迟封印与模型证据

- SessionEnd 不在三秒预算内扫描或封印事件链，只生成带 HMAC 的最小 job 并启动 detached worker；
- worker 负责幂等追加 `SESSION_ENDED`、验证完整链、形成 seal 和提交 done 证据；
- job、事件和 seal 同时绑定 `project_id + repo_fingerprint`，跨项目复制失败关闭；
- `requested_model_policy`、`runtime_model_evidence`、`diagnostic_model_observation` 分别记录请求上限、可信宿主证明和诊断旁证；
- 没有外部宿主信任锚时，`runtime_model_evidence` 必须为 `UNAVAILABLE`；
- 已关闭 segment 可非破坏复制到 archive，并由不可变 manifest 哈希链验证；归档不删除 canonical Event、Snapshot 或 Proposal。
