# V7.4.3 发行说明

版本：7.4.3
宿主窗口：Codex CLI 0.153.2 与此前十个稳定发行版

## 核心修正

- 宿主实际模型身份与推理强度不再属于 Agent 的输入、证据或治理条件；运行时不读取、不推断、不保存、不证明，也不据此计费、评分或决定发布。
- 自动派发只使用 `luna-low`、`luna-medium`、`terra-medium`、`terra-high` 四个抽象批准档位。精确模型请求只允许在 PreToolUse 宿主适配器中短暂校验，持久状态只保留批准档位、permit 引用和预留单位。
- TaskOutcomeEvent 升级为 V3，DelegationBudget 升级为 V2，Reviewer 结果升级为 V4；三者均移除宿主运行时模型身份合同。
- 校准和 Evolution 改为比较批准档位的结果价值与单位成本，不再生成基于宿主模型身份的升级信号。

## 兼容与迁移

- V7.4.2 及更早版本的 Event V2 与 Budget V1 链仍先按原始合同验证哈希/HMAC，再通过允许字段投影供新版本只读使用。
- 新旧事件链、新旧预算链物理分离；新版本拒绝向旧链追加，也拒绝不同 schema 混写。
- 历史记录中的模型身份字段不会进入 V3 聚合、Snapshot、Assessment、Proposal、Reviewer 状态或发布报告。
- Reviewer 旧状态迁移只保存安全投影，不重新序列化旧运行时模型信息。

## 发布门禁

- 新增隐私边界静态检查、派发策略验收、Lifecycle Acceptance V2 与 Release Attestation V2。
- 发布报告只证明批准档位门禁、预算预占、生命周期关联、链完整性与隐私扫描；不证明宿主实际运行了哪个模型。
- V7.4.3 保持 V7.4.2 的 Codex CLI 0.153.2 冻结兼容窗口，不顺带扩展到未来版或预发布版。

## 当前状态

Windows 账户级事务重装、Plugin 启用/版本/payload 读回以及已安装 Hook 生命周期封印已通过。远程 CI、标签和公开 Release 不在本文件中预先宣称完成，最终状态以发布后读回为准。
