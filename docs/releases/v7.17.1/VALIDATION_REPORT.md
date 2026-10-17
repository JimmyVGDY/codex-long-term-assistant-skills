# V7.17.1 验证记录

## 官方基线与冻结证据

- OpenAI 官方更新日志、npm `latest` 与 GitHub 最新 Release 均确认 0.163.0 / `rust-v0.163.0` 为非预发布稳定版。
- 标签提交：`83086188ae0614bd882818ff1aa23f3194962012`。
- npm tarball SHA-256：`1a71db36560bb446d2c2e63ae675c4a3018c38ace38ca533f8d1b25d3e6555b4`。
- discovery：`763704f5ae5f227d186dae8f5339edd6fde4f4a54c88c8ffb5ef9ad1b5a368eb`；schema：`162735b4d0c021c911cb3939b6130d2aad90cf5f865069a17b97c0cf02c53e14`；apply_patch handler：`1256b2219f6acb9c49ae472860ee69d73c75bb427dcca4dae2a30018d30216c0`；context：`9a9acc6daab2112bd9ca1a07a1e1f2105b20a7f565878157c726ee0d7a3e00cc`。
- 闭合窗口为 0.163.0、0.162.1、0.162.0、0.161.0、0.160.1、0.160.0、0.159.2、0.159.1、0.159.0、0.158.0、0.157.1；顺序摘要为 `de1b6a2ab6d51be3a437d241afbee22572b9bf9ee2c3bb51e04bec01872153f6`。

## 当前源快照验证

- 兼容注册表契约：18 项通过。
- package-manager doctor 窗口读回：通过。
- 0.163.0 隔离 Windows CLI / Plugin / 合成 Hook 矩阵：通过；制品摘要与冻结注册表一致。
- 基线已从 V7.16.2 更新到公开 V7.17.0 后的 `fd43b7dc273d11cd4a9f06bde105986c4b63711a`，因此更新前证据均按规则标记为失效并重新执行。

完整包、运行库、文档、可复现构建、跨平台矩阵、独立复审、账户安装、实际 Desktop 进程、提交、推送、标签、Release、签署制品与公开下载属于后续独立门禁；只在真实执行和读回后更新为通过。

## 完整本地验证

- 主包证据：发现并执行 1359 项；1358 项通过，1 项按平台跳过，无失败或错误；报告 SHA-256 为 `da95c3e0f74baad4653aeb8d6f71a293e2307cc52cfbd4b9a02b791715a36157`。
- 运行库证据：发现并执行 265 项，全部通过；报告 SHA-256 为 `0e756adafd9ae2ad87d5408a439010e001a22c0d83d777d8f875fbc4db951e47`。
- `validation_evidence.py` 映射的 23 组必需能力全部为 `PASS`。
- 本机 Windows PowerShell 默认禁止脚本执行；安装器与统一 CLI 用例在仅限验证子进程的 `PSExecutionPolicyPreference=Bypass` 下重跑通过。机器级执行策略未修改，该环境差异单独保留，不写成产品修复。

## 官方源码与可复现构建

- 闭合窗口内 11 个官方标签、discovery、schema、apply_patch handler、context 摘要及固定断言已逐项在线复核，结果为 `PASS`；仓库外报告保存于本机临时证据目录。
- 中英文构建器的内部双次摘要一致，独立归档验证与跨调用逐字节比较通过；每个归档包含 946 项。
- 额外一次中文构建尝试因临时文件在替换前缺失而失败，保留为瞬时失败记录；重试通过且与成功归档逐字节一致。
- 最终标签资产、SHA256SUMS、双 witness 与 provenance 由标签工作流在提交后生成，必须在公开发布后读回；源文档不嵌入会改变自身归档内容的预构建 ZIP 摘要。
