# 历版发行资料

V7.3.0 是当前版本。下表中的其他版本仅用于发行追溯；其详情页会显示历史资料提示并从默认站内搜索排除，不能作为当前安装或操作说明。

English: [README.en.md](README.en.md)

发行证据按语义版本集中保存。每个目录只包含该版本实际存在的说明、构建信息、审计与验证材料；缺失文件不会以空白占位补造。

新版本的标签、可复现构建、签名来源证明和人工发布门禁见 [Release 自动化与制品来源证明](RELEASE_AUTOMATION.md)。

| 版本 | 发行说明 | 审计报告 | 验证报告 | 真实观察 | 构建信息 | 包验证 |
| --- | --- | --- | --- | --- | --- | --- |
| 7.3.0 | [查看](v7.3.0/RELEASE_NOTES.md) | [查看](v7.3.0/AUDIT_REPORT.md) | [查看](v7.3.0/VALIDATION_REPORT.md) | 3 条最终化记录、1 个任务，`INSUFFICIENT_DATA`，默认路由不变 | [JSON](v7.3.0/BUILD_INFO.json) | [JSON](v7.3.0/PACKAGE_VALIDATION.json) |
| 7.2.0 | [查看](v7.2.0/RELEASE_NOTES.md) | [查看](v7.2.0/AUDIT_REPORT.md) | [查看](v7.2.0/VALIDATION_REPORT.md) | 包内 `NOT_EVALUATED`；宿主证据独立保存 | [JSON](v7.2.0/BUILD_INFO.json) | [JSON](v7.2.0/PACKAGE_VALIDATION.json) |
| 7.1.0 | [查看](v7.1.0/RELEASE_NOTES.md) | [查看](v7.1.0/AUDIT_REPORT.md) | [查看](v7.1.0/VALIDATION_REPORT.md) | — | [JSON](v7.1.0/BUILD_INFO.json) | [JSON](v7.1.0/PACKAGE_VALIDATION.json) |
| 7.0.0 | [查看](v7.0.0/RELEASE_NOTES.md) | [查看](v7.0.0/AUDIT_REPORT.md) | [查看](v7.0.0/VALIDATION_REPORT.md) | [查看](v7.0.0/IMPLICIT_TRIGGER_OBSERVATION.md) | [JSON](v7.0.0/BUILD_INFO.json) | [JSON](v7.0.0/PACKAGE_VALIDATION.json) |
| 6.6.1 | [查看](v6.6.1/RELEASE_NOTES.md) | [查看](v6.6.1/AUDIT_REPORT.md) | [查看](v6.6.1/VALIDATION_REPORT.md) | — | [JSON](v6.6.1/BUILD_INFO.json) | [JSON](v6.6.1/PACKAGE_VALIDATION.json) |
| 6.6.0 | [查看](v6.6.0/RELEASE_NOTES.md) | [查看](v6.6.0/AUDIT_REPORT.md) | [查看](v6.6.0/VALIDATION_REPORT.md) | — | [JSON](v6.6.0/BUILD_INFO.json) | [JSON](v6.6.0/PACKAGE_VALIDATION.json) |
| 6.5.0 | [查看](v6.5.0/RELEASE_NOTES.md) | [查看](v6.5.0/AUDIT_REPORT.md) | [查看](v6.5.0/VALIDATION_REPORT.md) | — | [JSON](v6.5.0/BUILD_INFO.json) | — |
| 6.4.0 | [查看](v6.4.0/RELEASE_NOTES.md) | [查看](v6.4.0/AUDIT_REPORT.md) | [查看](v6.4.0/VALIDATION_REPORT.md) | — | [JSON](v6.4.0/BUILD_INFO.json) | — |
| 6.3.0 | [查看](v6.3.0/RELEASE_NOTES.md) | [查看](v6.3.0/AUDIT_REPORT.md) | [查看](v6.3.0/VALIDATION_REPORT.md) | — | [JSON](v6.3.0/BUILD_INFO.json) | — |
| 6.2.0 | [查看](v6.2.0/RELEASE_NOTES.md) | [查看](v6.2.0/AUDIT_REPORT.md) | [查看](v6.2.0/VALIDATION_REPORT.md) | — | [JSON](v6.2.0/BUILD_INFO.json) | — |
| 6.1.0 | [查看](v6.1.0/RELEASE_NOTES.md) | [查看](v6.1.0/AUDIT_REPORT.md) | [查看](v6.1.0/VALIDATION_REPORT.md) | — | [JSON](v6.1.0/BUILD_INFO.json) | — |
| 6.0.0 | [查看](v6.0.0/RELEASE_NOTES.md) | — | — | — | [JSON](v6.0.0/BUILD_INFO.json) | — |

这些资料描述各自版本当时的事实。当前宿主状态仍需通过安装器验证和 `codex plugin list --json` 独立读回。
