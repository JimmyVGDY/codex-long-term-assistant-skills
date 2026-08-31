# CHANGELOG

## 4.2.0 - 2026-08-12

### Added

- Luna Low、Luna Medium、Terra Medium、Terra High 四级自动子 Agent 模型路由；
- Reviewer 请求模型、运行时模型和策略状态审计；
- 审查包摘要、差异统计、文件状态和 freshness 检查；
- 相同 Reviewer/相同 packet、零发现重复轮次和 Terra High 升级理由保护；
- 检查点内容指纹与重复 append 自动跳过；
- Codex `config.toml` 分步配置指南、模型成本策略和 V4.2 设计文档；
- Reviewer 与检查点新增回归测试。

### Changed

- 默认复审预算从并行 6/累计 12/三轮收敛为并行 3/累计 6/两轮，保留显式兼容硬上限；
- 7 个 Reviewer 改为渐进读取、唯一职责、根因合并和结构化最小输出；
- 所有 Skill 增加模型与委派成本规则，辅助工作优先 Luna；
- 长期记忆从连续 5 个实质动作改为 8 个，恢复窗口从 5 个检查点降为 3 个，热区从 30 降为 20；
- 全局 `AGENTS.md` 压缩为跨项目核心规则，减少与 Skill Reference 重复。

### Compatibility

- 主 Agent 模型不被安装包改写；
- Reviewer TOML 不固定模型，动态派发仍可按风险升级；
- V4.1 高预算仍作为控制器硬上限存在，但普通流程不会自动启用。

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
