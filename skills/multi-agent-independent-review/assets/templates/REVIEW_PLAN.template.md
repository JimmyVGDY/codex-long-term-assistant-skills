# 多 Agent 复审计划

## 基本信息

- 任务标识：
- 功能边界：
- 审查阶段：pre / post
- 风险级别：低 / 中 / 高 / 关键
- 基线 Commit：
- 当前 HEAD：
- 差异范围：
- 最低定向验证：

## 运行时隔离

- Reviewer TOML 声明：
- 父会话实际沙箱：
- 是否确认使用指定 Agent：
- 探针结果：未执行 / sandbox-denied / permission-denied / write-succeeded / invalid
- 隔离等级：system-readonly / logical-readonly / self-review / unknown
- 是否要求严格只读：
- 是否满足严格只读资格：
- 隔离证据文件：

## 预算

- 默认最大深度：2
- 当前深度：0
- 实施前最大轮次：1
- 实施后默认最大轮次：2
- 当前轮次：1
- 实施前默认 Reviewer 上限：2
- 默认最大并行 Reviewer：3
- 默认 Reviewer 总量上限：6
- 已使用 / 剩余：0 / 6
- 默认最大集中修复轮次：2
- 默认 Terra High Reviewer 上限：1

## 当前轮 Reviewer

| Reviewer | 职责 | 范围 | 不负责 | 模型档位 | 状态 |
|---|---|---|---|---|---|
|  |  |  |  | luna-low / luna-medium / terra-medium / terra-high | 待启动 |

## 等待与归并规则

- [ ] 等待全部适用 Reviewer 返回后再修改代码
- [ ] Reviewer 行为只读，不允许修改或提交；若为 logical-readonly，已明确这不是系统隔离保证
- [ ] 主协调 Agent 统一去重、根因聚类和分级
- [ ] 形成最小完整修复集合后再集中修复
- [ ] 已检查 packet freshness，且没有相同 Reviewer / 相同 packet 的无理由重复派发

## 停止条件

-
