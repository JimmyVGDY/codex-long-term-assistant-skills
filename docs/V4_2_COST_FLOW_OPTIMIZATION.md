# V4.2 模型分级与流程收敛设计

## 一、优化目标

V4.2 在不删除 9 个 Skill、不减少 7 个专业 Reviewer 职责、不削弱证据和运行时隔离约束的前提下，重点收敛四类消耗：

1. 全局提示词重复内容；
2. 子 Agent 数量、并行数和复审轮次；
3. 父会话、完整 diff、日志和 Reference 的重复加载；
4. 简单任务错误使用 Terra High 或更高模型。

## 二、核心变化

### 2.1 全局上下文

- `global/AGENTS.md` 从 500 余行压缩为约 170 行；
- 领域细则继续留在 Skill References；
- 全局只保留跨项目边界、授权、证据、Skill 路由、模型路由和通用交付规则。

### 2.2 默认复审预算

| 项目 | V4.1 默认 | V4.2 默认 | 兼容硬上限 |
|---|---:|---:|---:|
| Agent 深度 | 3 | 2 | 3 |
| 实施前 Reviewer | 4 | 2 | 4 |
| 并行 Reviewer | 6 | 3 | 6 |
| 累计 Reviewer | 12 | 6 | 12 |
| 实施后轮次 | 3 | 2 | 3 |
| 集中修复轮次 | 3 | 2 | 3 |
| Terra High Reviewer | 未限制 | 1 | 2 |

保留硬上限是为了兼容关键生产或重大迁移，但必须在 `init` 时显式提高，普通任务不会自动使用。

### 2.3 渐进式审查包

审查包新增：

- `packet-summary.md`；
- `diff-stat.txt`；
- `name-status.txt`；
- 推荐读取顺序；
- diff 字节数和改动文件数；
- `freshness` 工作区新鲜度检查。

Reviewer 先读取摘要、统计和分配范围，只在需要证据时读取相关 patch hunks。完整 `diff.patch` 仍保留，避免以节省 Token 为由降低证据质量。

### 2.4 重复工作保护

- 相同 Reviewer 不得无理由重复审查相同 packet；
- 相同 packet 上一轮已经零发现时，禁止机械增加轮次；
- 相同 packet 的第二意见必须显式记录理由；
- 审查包过期后必须重建，不能继续引用旧结论；
- 长期记忆相同内容和相同 Git 指纹默认不重复写检查点。

### 2.5 检查点收敛

- 从“连续 5 个实质动作”调整为 8 个；
- 恢复默认只读最近 3 个检查点；
- 热区默认从 30 条降到 20 条；
- 检查点增加内容指纹，重复 append 自动跳过；
- 多 Agent 只在计划确定、归并完成、集中修复完成和最终结论等可恢复节点写共享检查点，不为每个派发事件单独写入。

## 三、典型流程

### 3.1 小任务

```text
主 Agent 识别 → 单 Agent 修改/核验 → 最低验证 → 交付
```

默认 0 个 Reviewer。只有明确的独立机械核验价值时使用 1 个 `luna-low`。

### 3.2 普通行为修改

```text
主 Agent Terra → 统一审查包 → 1～2 个 Reviewer
  ├─ Luna Medium：兼容/测试证据
  └─ Terra Medium：功能/业务
→ 统一归并 → 集中修复 → 受影响维度定向复核
```

默认最多 2 轮、累计最多 6 个 Reviewer。

### 3.3 高风险修改

```text
实施前 1～2 个 Reviewer
→ 主 Agent 实施与定向验证
→ 2～3 个实施后 Reviewer
  ├─ Luna Medium：基础扫描
  ├─ Terra Medium：专业判断
  └─ Terra High：唯一关键维度
→ 集中归并和修复 → 最多 1～2 个定向复核
```

`terra-high` 必须记录升级理由，不得因“deep”统一提升全部 Reviewer。

## 四、质量保护

优化可能带来的风险与保护措施：

| 风险 | 保护措施 |
|---|---|
| Reviewer 数量减少导致漏检 | 风险路由、职责互斥、公共审查包、必要时显式提高硬上限 |
| Luna 对业务语义理解不足 | 逐级升级；业务、数据和并发默认允许 Terra Medium |
| 摘要读取遗漏关键 hunk | 完整 diff 保留；Reviewer 可按证据需求读取相关 hunk 和直接依赖 |
| 过早停止复审 | 仅在相同 packet 零发现时自动停止；差异变化必须重建 packet |
| 运行时模型不可确认 | 记录 `unverified`，不宣称策略已被底层强制执行 |
| 可写父会话误称严格只读 | 继续区分 system-readonly、logical-readonly 和 unknown |

## 五、估算口径

不能仅凭模型名称精确预测实际 credits，因为上下文、工具调用、推理长度和输出量都会变化。V4.2 用以下可观测指标比较优化前后：

- 每任务启动的子 Agent 数；
- Luna/Terra 与 Low/Medium/High 分布；
- 每轮审查包是否复用或过期；
- 重复 Reviewer/相同 packet 拒绝次数；
- 实际复审轮次和集中修复轮次；
- 全局 AGENTS、Skill 和 Reference 加载字符数；
- `model_assignment` 的 confirmed/fallback/unverified/mismatch 数量。

建议在代表性小、中、高风险任务上各运行 5～10 次，再以真实 Codex 使用记录评估成本和漏检率。
