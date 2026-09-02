# Reviewer 结果

## 基本信息

- Reviewer：
- 结果 ID：由 `result-template` 生成，不手工改写
- 职责：
- 审查阶段：pre / post
- 轮次：
- 逻辑深度：
- 功能边界：
- 审查包 SHA-256：
- 基线 / 差异范围：
- 审查文件：
- 阅读的上游、下游和共享逻辑：
- 请求模型档位：luna-low / luna-medium / terra-medium / terra-high
- 最低可接受模型档位：luna-low / luna-medium / terra-medium / terra-high
- 请求模型 / 推理强度：
- 实际模型 / 推理强度：
- 模型分配状态：declared_match / fallback_acceptable / underpowered / unverified / mismatch
- 运行证据等级 / 来源：unavailable / declared；none / reviewer-result
- 模型分配说明：
- 任务难度：LOW / MEDIUM / HIGH / CRITICAL / UNKNOWN
- 耗时（毫秒）：
- 估算成本 / 公式版本：profile-weight-v1
- 校准归因是否最终完成：固定为否；由主协调 Agent 在修复验证后通过控制器另行最终化
- Reviewer 配置声明：
- 父会话实际沙箱：
- 运行时隔离等级：system-readonly / logical-readonly / self-review / unknown
- 是否满足严格只读资格：
- 隔离证据：
- 最终结论：通过 / 修订后通过 / 有非阻塞问题 / 有阻塞问题 / 未完成

## 发现

### FINDING-001

- 严重等级：阻塞 / 高 / 中 / 低 / 建议
- 证据等级：已确认 / 高概率 / 推测 / 未验证
- 文件、符号或配置位置：
- 问题描述：
- 触发条件：
- 影响范围：
- 根因判断：
- 是否由本次改动引入：是 / 否 / 未确认
- 建议修复边界：
- 修复后验证：
- 可合并的问题：
- 处置：PENDING / ACCEPTED / REPAIRED / REGRESSION_PREVENTED / REJECTED / DEFERRED / OUT_OF_SCOPE / DUPLICATE / INSUFFICIENT_EVIDENCE
- 采纳原因：CORRECTNESS / SECURITY / COMPATIBILITY / PERFORMANCE / DATA_CONTRACT / REGRESSION_PREVENTION / 其他允许值
- 已修复：是 / 否
- 已防止回归：是 / 否
- 回归证据：

## 未验证项

-

## 建议追加专项复审

- 是否建议：是 / 否
- 原因：
- 建议维度：

> Reviewer 按行为规则只报告、不修改、不提交、不继续派生；同一根因合并，默认最多 8 组。只有 isolation=system-readonly 时，才能声明系统级写入隔离。
