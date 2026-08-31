# Codex 跨项目长期技术助手 V6.4 发布说明

## 发布定位

V6.4 面向 Windows 原生 Codex CLI 0.150.1，重点强化 Plugin 载荷身份、安装恢复、事件分段与统一发行验证。V6.3 的 10 个 Skill、7 个 Reviewer、6 个 Hook、TaskOutcomeEvent 2.0、项目双重隔离和 Terra High 自动上限保持兼容。

## 主要变化

### ZIP 到运行 cache 的身份链

- 新增 `PLUGIN_PAYLOAD_MANIFEST.json`，只覆盖 `.codex-plugin`、`skills`、`hooks`、`runtime` 四个运行载荷根；
- 对条目路径、文件大小和 SHA-256 采用规范化排序；
- ZIP、Marketplace 源和 Plugin cache 按同一投影计算 digest；
- 未知载荷、路径越界、符号链接、Junction 或 Reparse Point 均失败关闭；
- `verify-release.py` 将制品、宿主、Plugin、生命周期和 payload 证据汇总为单一结论。

### V6.3 到 V6.4 可恢复升级

- 安装状态由 schema 1 显式迁移到 schema 2，保留未知字段、旧备份引用和历史状态；
- Marketplace 仅更新本包 payload 子树并合并本包 manifest 条目，不替换未知资产；
- Plugin cache 候选路径、旧/新 digest、备份、激活后读回和恢复动作纳入事务 journal；
- 在 Plugin add、cache 校验和 state 写入等硬崩溃边界完成恢复测试；
- 受管树任意后代链接型路径在摘要、备份、复制和删除前递归拒绝。

### 事件安全分段与宿主事实

- TaskOutcomeEvent V2 写入支持连续 segment；
- 读取、生命周期验收与自观察统一使用跨段校验入口；
- 活动文件半记录被隔离为审计文件，完整事件链继续使用；
- 死进程锁可恢复，存活持有者不可因时间阈值被抢占；
- 显式非法终态、未知实际模型、哈希自洽但 schema 非法的旧记录均失败关闭；
- `actual_model`、`actual_reasoning_effort`、`terminal_outcome` 只接受明确宿主字段，不从通用别名推断。
- 生命周期验收器将 Hook 实际字段与 Codex 子任务会话证据分层验证：宿主未向 Hook 暴露模型时保持 `unavailable`，同时可通过父会话、子任务 turn、模型和推理强度的关联事实完成 Reviewer 验收。

### Codex 能力探测

- `doctor` 在写入前确认 Codex 0.150.1；
- 检查 `plugin list --json`、Marketplace add/remove、Plugin add/remove 的实际命令能力；
- 未知版本、能力缺失或 Plugin 精确版本读回失败时停止安装并保留诊断信息。

## 兼容与安全边界

- 支持从 6.1.0、6.2.0、6.3.0 升级；
- 保留历史项目上下文、Event、Snapshot、Assessment、Proposal 和升级备份；
- `execution_authorization=NONE`；
- 不改写主 Agent 模型配置；
- Reviewer TOML 不固定模型；
- 自动路线保持 Luna Low → Luna Medium → Terra Medium → Terra High；
- 不自动接受或实施 Proposal；
- 不自动提交、推送、部署、重启或操作生产环境。

## 验收说明

包内回归、独立复审和候选实现证据记录于 `VALIDATION_REPORT_V6.4.md` 与 `V6.4_AUDIT_REPORT.md`。正式 ZIP、真实账户 Plugin 状态和生命周期证据只有在统一验证器与包外 attestation 同时通过后，才构成完整发行结论。
