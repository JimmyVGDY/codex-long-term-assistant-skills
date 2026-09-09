# V7.6.0 发行说明

V7.6.0 新增外部能力索引和可选流程门禁。开发 Skill 查找已有模块，从业务语义、兼容性、权限、状态、性能、测试负担与维护成本判断复用方式，并记录有依据的独立实现决定。

索引在仓库外保存有界源码定位与核验事实，支持初扫和增量维护；指纹匹配不会自动批准业务复用。项目门禁默认关闭，显式启用后增加写前准备及结束时的当前证据检查；冷索引局部例外仅覆盖一个既有文件。

原有 11 个 Codex 版本兼容窗口不变，从 7.5.1 使用现有事务安装器升级。不自动为业务项目启用门禁，不自动晋升稳定记忆。

[能力索引契约](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/blob/v7.6.0/docs/CAPABILITY_INDEX.md) · [验收规程](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/blob/v7.6.0/docs/COMPONENT_REUSE_ACCEPTANCE.md) · [验证报告](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/blob/v7.6.0/docs/releases/v7.6.0/VALIDATION_REPORT.md) · [审计报告](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/blob/v7.6.0/docs/releases/v7.6.0/AUDIT_REPORT.md) · [发行流程](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/blob/v7.6.0/docs/releases/RELEASE_AUTOMATION.md)。
