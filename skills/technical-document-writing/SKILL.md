---
name: technical-document-writing
description: >-
  技术方案、架构设计、实施方案、接口或数据库文档、部署手册、故障报告、代码审查报告、管理报告、README、Markdown 重构或基于现有资料整理正式文档时使用。仅更新 CHANGELOG、提交信息或代码注释通常不单独触发。
---

# 技术文档与正式报告编写技能

## 执行原则

1. 先读取 `references/technical-document-writing-rules.md` 索引；根据文档类型按需读取 `references/document-type-playbooks.md`，不得一次加载全部模板。
2. 明确读者、用途、决策问题、范围、事实来源、交付格式和修改权限。
3. 输入材料、代码、配置、日志和验证结果是主要依据；区分已确认、外部资料、工程推断、假设和未验证。
4. 从 `assets/templates/` 选择最接近模板并裁剪；简单文档不机械套完整结构。
5. 技术细节组合 Java、Python、`frontend-engineering`、数据基础设施或可观测性 Skill。
6. 文档与代码修改、测试、CHANGELOG、提交或发布绑定时组合 `$engineering-quality-delivery`；内部任务状态组合 `$long-running-task-memory`，不得混入正式文档。
7. 完成后检查准确性、完整性、一致性、可执行性、可维护性、安全性和读者可读性。

## 模型与委派成本

主 Agent 保持当前选择。子 Agent 的型号、思考强度和预算采用[脚本决策与弹性规则](../multi-agent-independent-review/references/script-first-routing.md)；执行脚本返回的精确参数。

- 新默认覆盖 GPT-6 Luna、Sol、Astra 的 low/medium/high；信息不足采用 Sol/medium，不以缺少理由、收益卡或历史样本阻止派发。
- 模型保留语义判断和调整建议；脚本在既有权限、总预算和允许调整范围内重新计算后才改变调用参数。规模或单次检查失败不直接代表难度，也不必然升档。
- 可计算的读取、去重、计数、预留和重试交脚本。缺证据走默认/降级路径，允许继续与验证通过分开记录。
- 复杂技术结论优先由领域 Skill 形成，本 Skill 负责结构化表达，避免在文档阶段重复高强度推理。

## 边界

- 不编造项目现状、版本、测试、性能、工期、预算和生产状态。
- 不因写文档自动获得代码、配置、数据库、Git 或环境修改权限。
- 未实际生成和验证文件时，不声称已创建 DOCX、PDF、图表或附件。
