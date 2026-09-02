# V7.3.0 包内与本机安装验证报告

English: [VALIDATION_REPORT.en.md](VALIDATION_REPORT.en.md)

版本：7.3.0

验证日期：2026-09-02

## 当前状态

包内与本机发布前验证已通过：170 项 package 测试、6 项 runtime 测试和 45 项 Skill 路由回归全部 PASS，语义、本地化、Markdown 链接、payload 身份和工作区零副作用门禁通过；中文、英文发行包均完成两次全新构建并在同语言内逐字节一致。

V7.3.0 payload 固定为 180 个受管文件，摘要为 `4f0168e4014440185a958f207931d01e73e4ca73207ee318ed0fcbee2a85a6d0`。账户级强制升级识别 `from_version=7.2.0` 与 `to_version=7.3.0`，受管备份、安装和 verify 均成功；Marketplace 与版本化 Plugin cache 的文件数量和摘要与源码一致，升级事务已清空。

本次真实校准观察保留 3 条已最终化记录、1 个独立任务和完整成本覆盖；两个 Reviewer 信号均为 `INSUFFICIENT_DATA`，没有生成路由提案，默认档位保持不变。该观察证明失败关闭与数据口径，不构成扩大样本量后的收益结论。

`codex plugin list --json` 已精确读回 `installed=true`、`enabled=true`、`version=7.3.0`。公开 Release 下载后的 ZIP 仍需在发布后独立校验来源证明、摘要、包结构和重装读回。

## 固定验收门禁

- Manifest、Plugin、payload、验证器、发行脚本与双语当前文档版本一致
- package/runtime 全量测试与 45 项路由回归通过
- 中文、英文发行包分别完成两次全新构建且同语言逐字节一致
- 本机账户级 Plugin 强制重装和 verify 通过
- `codex plugin list --json` 精确读回 7.3.0 已安装且已启用
- 公开附件通过 GitHub Artifact Attestations、SHA256SUMS、构建见证和下载后重装核对

提交、推送、标签、GitHub Release 与公开制品不属于包内验证范围；这些状态必须在各自动作后从 Git、GitHub 或本机安装状态独立读回。
