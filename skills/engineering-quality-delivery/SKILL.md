---
name: engineering-quality-delivery
description: >-
  代码、脚本、迁移或逻辑配置发生行为变化，或任务涉及测试、Git、CHANGELOG、审批、部署、重启、灰度、回滚和生产操作时使用。只读解释、无行为变化文字修改和普通文档排版通常不触发；多 Agent 复审仅按风险组合。
---

# 研发质量与安全交付技能

## 必读与执行档位

1. 先读取 `references/engineering-quality-delivery-workflow.md` 索引。
2. 从 `references/execution-profiles-and-phases.md` 选择 `LIGHT / STANDARD / STRICT`，不得因为本技能被激活就机械执行最重流程。
3. 非简单任务使用 `references/task-execution-envelope.md` 记录 Project Binding、六个路由维度、授权、Skill、门禁、停止条件和阶段。
4. 修改后按 `references/evidence-fingerprint-protocol.md` 记录验证和复审证据；代码、配置或差异变化后旧证据必须标记为 `stale`。
5. 受保护操作和最终交付读取 `references/project-binding-approval-finalization.md`，不得用 Evidence 替代 Approval，也不得把“已修改”表述为“已部署或已生效”。

## 强制流程

1. 确认项目、分支、基线、目标、非目标、授权、验收和停止条件；跨会话、非简单或受保护操作优先绑定仓库外 Project Profile。
2. 高风险公共契约、迁移、权限、核心状态机、跨服务和生产方案，在编码前按需组合 `$multi-agent-independent-review` 完成一次实施前门禁。
3. 做当前功能边界的最小充分修改，并执行与改动直接相关的最低定向验证。
4. 实施后独立复审只在真实行为改动且风险需要时触发；低风险、无行为变化或只读任务不得机械多开 Reviewer。
5. 复审后再修改时，受影响验证、Review Packet 和复核结论自动失效并重新执行。
6. Git 提交、推送、部署、重启、数据写入和功能生效分别授权、分别执行、分别读回、分别报告。
7. 最终交付从当前仓库、Evidence、Approval 和动作读回记录重新生成，不沿用旧基线或被否决的中间方案。

## 模型与委派成本

- 构建结果、测试报告、覆盖率、diff 和交付证据收集优先 `luna-low`；范围明确的测试缺口和兼容核对使用 `luna-medium`。
- 普通回归范围、实施边界和交付判断使用 `terra-medium`；生产、不可逆迁移、复杂回滚或阻塞冲突才使用 `terra-high`。
- `STRICT` 只表示流程门禁更严格，不自动把主 Agent 或全部 Reviewer 升级到 High；证据可复用时禁止重复执行等价验证。

## 工具

- Task Envelope V2、门禁、Approval 消费与 Finalization：`scripts/execution_guard.py`
- 项目 Onboarding、Approval、Evidence、记忆晋升和 Finalization：安装后的 `cp-runtime.py`，源码入口为包根目录 `scripts/cp-runtime.py`
- 模板：`assets/templates/TASK_EXECUTION_ENVELOPE.template.yaml`

## 组合边界

- 应用机制组合 Java、Python、`frontend-engineering` 或数据基础设施 Skill，不无条件加载全部。
- 只读可观测性分析优先 `$log-observability-analysis`；明确转入修复后才执行本技能交付门禁。
- 正式文档组合 `$technical-document-writing`；跨会话或多节点任务组合 `$long-running-task-memory`。
