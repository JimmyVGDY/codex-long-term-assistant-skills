# CHANGELOG

## 4.1.0 - 2026-07-31

### Added

- LIGHT/STANDARD/STRICT 执行档位与阶段状态机；
- 任务执行信封、证据指纹和自动失效；
- Reviewer 统一审查包、结构化结果 Schema 和成本档位；
- 子 Agent 独立上下文委派协议；
- dry-run、doctor、备份 manifest 和一键恢复；
- 语义一致性校验；
- Codex 用户 Skill 路径自适应与旧路径重复检测；

### Changed

- Java、Python、数据、质量、可观测性、长期记忆、多 Agent 复审和技术文档的大 Reference 改为按需分片；
- 质量 Skill 不再默认对所有改动机械要求完整多 Agent 复审；
- Reviewer 使用独立上下文，只接收最小审查包并返回结构化摘要；
- 修复 review_controller 中“父会话声明只读但写入探针成功”仍可能判为系统只读的问题；
- 清理过时 Vue/v3.2 语义和脚本相对路径。
