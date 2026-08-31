# 子 Agent 模型分级与成本策略

## 一、目标

在保留独立上下文、专业复审和关键风险判断的前提下，降低不必要的子 Agent 数量、重复上下文、重复扫描和高强度推理。

本策略只约束本安装包自动发起的子 Agent 工作流。主 Agent 继续使用用户当前选择的模型；用户在本工作流之外手工启动的 Agent 不受 `review_controller.py` 强制拦截。

## 二、三个互不等价的维度

| 维度 | 可选值 | 控制内容 |
|---|---|---|
| 执行流程 | `LIGHT / STANDARD / STRICT` | 授权、验证、回滚和交付门禁 |
| Reviewer 成本 | `economy / balanced / deep` | Reviewer 数量、范围、上下文和轮次 |
| 模型档位 | `luna-low / luna-medium / terra-medium / terra-high` | 模型和推理强度 |

`STRICT` 不等于 `terra-high`，`deep` 也不代表所有 Reviewer 都使用 High。

## 三、四级模型档位

| 档位 | 模型 | 推理强度 | 典型任务 |
|---|---|---|---|
| `luna-low` | `gpt-5.6-luna` | `low` | 文件/符号定位、提取、分类、格式化、状态与测试结果机械核对 |
| `luna-medium` | `gpt-5.6-luna` | `medium` | 有界日志归类、普通兼容扫描、测试证据审查、明确范围的只读分析 |
| `terra-medium` | `gpt-5.6-terra` | `medium` | 业务语义、多文件调用链、常规实现、专业审查和综合判断 |
| `terra-high` | `gpt-5.6-terra` | `high` | 复杂事务、并发竞态、鉴权越权、不可逆迁移、核心状态机和冲突裁决 |

自动升级链固定为：

```text
luna-low → luna-medium → terra-medium → terra-high
```

自动流程禁止使用 `gpt-5.6-sol`、`xhigh`、`max` 和 `ultra`。自动上限是 `terra-high`。

## 四、升级与降级条件

### 4.1 允许升级

- Luna 无法给出有证据支撑的结论；
- 需要理解业务口径或多文件调用链；
- 出现多个相互冲突的证据或 Reviewer 结论；
- 涉及事务、锁、并发、幂等、权限、数据迁移或不可逆操作；
- 当前任务的失败成本明显高于升级成本。

### 4.2 不允许仅因以下原因升级

- 文件数量多、日志很长；
- Skill 数量多；
- 任务持续时间长；
- 处于 `STRICT` 流程；
- 已进入第二轮或第三轮；
- 父 Agent 使用 Terra High。

### 4.3 降级优先

- 证据提取、测试输出归纳和状态核对优先 Luna；
- 修复后定向复核范围比第一轮更窄时，应保持或降低档位；
- 运行时实际使用更低批准档位时，结果记录为 `fallback`，不视为违规；
- 运行时档位高于请求或落入四级之外，记录为 `mismatch`，关闭台账前必须显式确认。

## 五、各类 Reviewer 默认路由

| Reviewer | 默认 | 升级条件 |
|---|---|---|
| 测试与交付 | `luna-low` | 回归范围复杂时 `luna-medium` |
| 回归与兼容 | `luna-medium` | 公共接口、历史数据、新旧版本共存时 `terra-medium` |
| 性能与资源 | `luna-medium` | SQL/锁/线程池/容量模型复杂时 `terra-medium` 或 `terra-high` |
| 功能与业务 | `terra-medium` | 核心状态机、资金或复杂业务口径时 `terra-high` |
| 权限与安全 | `terra-medium` | 认证、越权、租户隔离和高影响漏洞时 `terra-high` |
| 数据与契约 | `terra-medium` | 迁移、事务、MQ 成功边界和不可逆变更时 `terra-high` |
| 状态与并发 | `terra-medium` | 竞态、锁顺序、幂等、补偿和恢复时 `terra-high` |

同一边界默认最多 1 个 `terra-high` Reviewer；显式放宽后硬上限为 2。

## 六、成本档位映射

| Reviewer 档位 | 默认模型 | Reviewer 数量 | 说明 |
|---|---|---:|---|
| `economy` | `luna-low` | 0～1 | 小任务优先不启动子 Agent |
| `balanced` | `luna-medium` | 1～2 | 有业务判断时其中 1 个可用 `terra-medium` |
| `deep` | `terra-medium` | 2～3 | 仅关键维度使用 `terra-high` |

映射是默认值，不是强制让同轮所有 Reviewer 使用同一档位。每个 Reviewer 按唯一职责独立选择。

## 七、配置与优先级

推荐在用户 `config.toml` 中设置低成本兜底：

```toml
[agents]
enabled = true
max_concurrent_threads_per_session = 3
default_subagent_model = "gpt-5.6-luna"
default_subagent_reasoning_effort = "medium"
```

保留 `agents.interrupt_message` 的 Codex 默认值 `true`。关闭它只能节省极少量中断提示上下文，却可能降低中断恢复时的语义完整性。

现有专业 Reviewer TOML **故意不写死** `model` 和 `model_reasoning_effort`，以便主协调 Agent 在派发时动态指定。若 Agent TOML 写死模型，文件配置会覆盖 spawn 和 `[agents]` 默认值，动态降级将失效。

## 八、可审计性

`review_controller.py dispatch` 记录：

- 请求档位、模型和推理强度；
- `terra-high` 升级理由；
- 相同 packet 重复派发理由；
- 当前隔离等级和 packet hash。

Reviewer 结果记录运行时模型（能够确认时）和状态：

- `confirmed`：与请求一致；
- `fallback`：使用更低批准档位；
- `unverified`：运行时信息无法确认；
- `mismatch`：高于请求、超出 Luna/Terra 或使用未批准组合。

控制器能约束通过它登记的自动派发，但不能阻止用户在工作流外手工启动更高模型。最终报告必须如实说明这一边界。
