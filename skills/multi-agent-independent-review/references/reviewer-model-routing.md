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

主协调 Agent 可按职责覆盖默认值，但必须记录原因。高风险边界默认最多 1 个 `terra-high` Reviewer；只有用户或项目规则显式放宽且不超过控制器硬上限时才允许 2 个。

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

## 六、运行时确认

- 自定义 Reviewer TOML 有意不固定 `model` 和 `model_reasoning_effort`，避免高优先级静态配置阻断动态路由。
- 派发前由 `review_controller.py` 记录请求档位；Reviewer 结果必须回传实际模型和推理强度。
- 实际档位低于请求记为 `fallback`；高于请求或超出四级批准档位记为 `mismatch`。
- 控制器只约束本 Skill 的派发台账，不能替代 Codex 平台级 allowlist；主协调 Agent 必须显式按台账档位启动子 Agent。
