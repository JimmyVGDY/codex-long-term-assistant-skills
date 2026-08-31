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

- 格式整理、字段提取、模板填充、README 和既有材料重构优先 `luna-low`；接口/代码证据归纳和普通正式文档使用 `luna-medium`。
- 多方案综合、架构取舍和跨材料冲突判断使用 `terra-medium`；高风险架构、事故归因或不可逆方案论证才使用 `terra-high`。
- 复杂技术结论优先由领域 Skill 形成，本 Skill 负责结构化表达，避免在文档阶段重复高强度推理。

## 边界

- 不编造项目现状、版本、测试、性能、工期、预算和生产状态。
- 不因写文档自动获得代码、配置、数据库、Git 或环境修改权限。
- 未实际生成和验证文件时，不声称已创建 DOCX、PDF、图表或附件。
