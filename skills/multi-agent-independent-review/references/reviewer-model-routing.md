# Reviewer 模型路由与升级策略

## 一、四级批准档位

自动 Reviewer 只允许以下档位：

| 档位 | 模型 | 推理强度 | 典型工作 |
|---|---|---|---|
| `luna-low` | `gpt-5.6-luna` | `low` | 搜索、提取、分类、清单核对和机械证据检查 |
| `luna-medium` | `gpt-5.6-luna` | `medium` | 范围明确的只读分析、兼容扫描、测试证据复核 |
| `terra-medium` | `gpt-5.6-terra` | `medium` | 业务语义、多文件逻辑、专业工程判断和普通复杂审查 |
| `terra-high` | `gpt-5.6-terra` | `high` | 事务、并发、安全、不可逆迁移、核心状态机和阻塞冲突裁决 |

升级链固定为：

```text
luna-low -> luna-medium -> terra-medium -> terra-high
```

自动流程禁止使用 Sol、`xhigh`、`max` 和 `ultra`。`terra-high` 是自动 Reviewer 的硬性策略上限，不是默认值。

## 二、三类档位互相独立

| 维度 | 取值 | 控制内容 |
|---|---|---|
| 执行流程 | `LIGHT / STANDARD / STRICT` | 授权、验证、回滚和交付门禁 |
| Reviewer 成本 | `economy / balanced / deep` | Reviewer 数量、范围和上下文预算 |
| 模型档位 | 四级批准档位 | 单个 Reviewer 的模型与推理强度 |

流程严格不等于推理强度高；`deep` 也不等于全部 Reviewer 使用 `terra-high`。

## 三、默认映射

| 成本档位 | 默认模型档位 | 默认 Reviewer 数量 |
|---|---|---:|
| `economy` | `luna-low` | 0～1 |
| `balanced` | `luna-medium` | 1～2 |
| `deep` | `terra-medium` | 2～3 |

主协调 Agent 可按职责覆盖默认值，但必须记录原因。高风险边界默认最多 1 个 `terra-high` Reviewer；只有明确授权或项目规则显式放宽且不超过控制器硬上限时才允许 2 个。

## 四、按 Reviewer 职责选择

| Reviewer | 常态档位 | 升级条件 |
|---|---|---|
| 测试与交付 | `luna-low` | 回归范围复杂时 `luna-medium`；通常不使用 Terra High |
| 回归与兼容 | `luna-medium` | 公共接口、历史数据、新旧版本共存时 `terra-medium` |
| 性能与资源 | `luna-medium` | SQL、锁、线程池、容量或高频路径判断时 `terra-medium`；复杂并发资源争用可 `terra-high` |
| 功能与业务 | `terra-medium` | 核心业务状态机、资金、库存或口径冲突时 `terra-high` |
| 权限与安全 | `terra-medium` | 认证、越权、租户隔离或高权限入口时 `terra-high` |
| 数据与契约 | `terra-medium` | 事务、迁移、MQ 成功边界或不可逆数据变化时 `terra-high` |
| 状态与并发 | `terra-medium` | 竞态、锁顺序、幂等、补偿或复杂时序时 `terra-high` |

## 五、升级与降级

允许升级的证据：

- 当前档位无法形成有证据的结论；
- 需要解释业务语义或复杂跨模块调用链；
- 存在相互冲突的有效证据；
- 命中事务、并发、安全、不可逆迁移或核心状态机风险。

以下不能单独作为升级理由：文件多、日志长、Skill 多、任务持续时间长、流程为 `STRICT`、已进入第二轮。

优先降级或停止：

- 子任务只是搜索、清单核对、格式化或证据提取；
- 已有证据足以裁决；
- 相同 Reviewer 已审过相同 packet；
- 上一轮已对相同 packet 无问题通过；
- 继续扩大范围不会改变门禁结论。

## 六、派发约束

- Reviewer TOML 保持模型和强度未固定；协调者按控制器记录的批准档位派发。
- 派发前记录批准档位、最低可接受档位和 permit 引用；最低档位不能高于批准档位。
- 结果必须匹配任务、边界、轮次、packet 和派发约束。请求档位是策略约束，不证明实际运行模型。
- 不读取、推断、保存或导出宿主模型身份，不请求 Reviewer 自报模型。
- 根任务 DelegationBudget 管理预占与成本；未激活账本时只有模型上限生效，不宣称预算门禁通过。

## 七、INLINE 决策与校准

- 无需子 Agent 时，先用 `route --decision INLINE` 追加阶段决策。它不创建轮次、不增加 Reviewer 计数，也不消耗模型预算。
- 新建台账在 `plan` 前必须先记录 `INLINE` 或 `DELEGATE`；迁移自 v4 及更早版本的台账保留无决策兼容路径。
- 最新决策为 `INLINE` 时，`plan` 与 `dispatch` 都会失败。只有首轮计划前，提供前一 decision id、改判原因和新证据，才能追加 `DELEGATE` 改判；历史决策不可覆盖。
- Reviewer v4 结果包含任务难度、耗时、待定归因和版本化估算成本，并拒绝 schema 外字段；Reviewer 文件中的 `calibration_finalized` 必须为 `false`。主协调 Agent 在修复和验证后，使用 `finalize-calibration` 携带证据单独最终化归因。
- 控制器以 `task_id + reviewer + result_id` 投影到 `review-results.jsonl`；估算成本由批准派发档位确定，投影不包含宿主实际模型身份。
- `validate` 会核对投影台账与 `review-state`；若进程中断造成不一致，使用 `sync-calibration` 从权威状态确定性重建。
- `profile-weight-v1` 权重为 1/2/4/8。缺失或非法成本保持 unknown；只有控制器最终化后的记录才参与低收益判断。
