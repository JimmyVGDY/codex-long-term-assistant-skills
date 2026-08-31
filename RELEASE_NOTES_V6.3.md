# Codex 跨项目长期技术助手 V6.3 发布说明

## 发布定位

V6.3 在 V6.2 Windows 原生 Codex CLI 0.150.1 兼容基线上，强化安装事务、发行证明和自观察证据质量。10 个 Skill、7 个 Reviewer、6 个 Hook、TaskOutcomeEvent 2.0、项目双重隔离和 Terra High 自动上限保持兼容。

## 主要变化

### 持久化安装事务

- 首次受管写入前建立事务日志和互斥锁；
- 记录备份、文件动作、Plugin 注册动作和提交状态；
- 增加 `status` 与 `recover`，支持进程中断后的确定性恢复；
- 恢复时检查归属漂移、链接型路径和备份完整性；
- 成功提交后归档事务，活动事务不残留。

### 可复现发行与机器证明

- 固定 ZIP 条目顺序、时间戳、文件模式和压缩参数；
- 两次独立构建必须字节一致；
- 发行证明绑定正式 ZIP SHA-256、Codex 0.150.1、Plugin 6.3.0 状态和验证证据哈希；
- 支持证据篡改检测与可选 HMAC 完整性认证。

### 真实生命周期验收

- 验收同一真实 Codex 会话中的 `TURN_OPENED`、`SUBAGENT_STARTED`、`SUBAGENT_STOPPED`、`TASK_COMPLETED`、`SESSION_ENDED`；
- 校验事件顺序、任务关联、项目身份、仓库指纹和完整哈希链；
- 对外报告只保留散列化会话与任务引用。

### 自观察质量与 Reviewer 归因

- 增加任务与会话生命周期完整率、SessionEnd 覆盖率；
- 识别缺失、重复、乱序和跨任务/跨会话串线；
- 增加实际模型、明确终态、项目与仓库绑定覆盖率；
- Reviewer 收益改为基于发现归因、采纳、修复、重复、回归预防、时长和成本代理；
- 样本或因果证据不足时输出 `insufficient-evidence`，不以发现数量代替收益。

## 兼容与安全边界

- 兼容从 V6.1.0、V6.2.0 升级；
- 保留旧状态结构与历史项目上下文；
- `execution_authorization=NONE`；
- 不自动接受或实施 Evolution Proposal；
- 不自动修改 Skill、Reviewer、主 Agent 模型或业务仓库；
- 不自动提交、推送、部署、重启或操作生产环境；
- 自动子 Agent 路线保持 Luna Low → Luna Medium → Terra Medium → Terra High，最高 Terra High。

## 验收状态

源码测试、独立复审、正式 ZIP 哈希、真实 Plugin 升级和生命周期实机证据以 `VALIDATION_REPORT_V6.3.md`、`V6.3_AUDIT_REPORT.md` 及包外机器证明为准。未产生对应证据前，不应把计划状态解释为已完成。
