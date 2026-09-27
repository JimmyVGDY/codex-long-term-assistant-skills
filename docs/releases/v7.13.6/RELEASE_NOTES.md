# V7.13.6 发行说明

V7.13.6 修复 Codex Desktop V1 委派接口的预算拦截遗漏。V1 创建工具由宿主归一为 `spawn_agent`，消息与恢复工具则保留 `multi_agent_v1send_input` 和 `multi_agent_v1resume_agent` 名称；这两种请求现在进入既有 PreToolUse 预算门禁。

- 仅登记两个精确名称，不新增通配 Hook；未绑定预算的任务继续保持原有中性行为。
- 保留已有创建、PostToolUse 回执、正文摘要与独立上下文检查，历史账本不重置。
- 本机真实 Desktop V1 拒绝重入对照通过；一次 GPT-6 Luna / Low 派发形成预占、真实创建回执、完成记录和一次/一单位扣减。
- 传输验收返回 UNKNOWN / ADMISSION_ONLY，不构成质量评测。冻结 V3、GPT-5.6 兼容及 GPT-6 场景资格门槛保持不变；其他桌面接口仍需各自验收。

产品仅支持 Codex Desktop。提交、CI、制品、公开发布、安装及生效分别核验。
