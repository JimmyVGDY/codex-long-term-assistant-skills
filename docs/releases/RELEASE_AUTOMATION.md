# Release 自动化与制品来源证明

English: [RELEASE_AUTOMATION.en.md](RELEASE_AUTOMATION.en.md)

## 目标

发行工作流把“源码验证、可复现构建、来源证明、Release 页面公开”拆成不同事实，防止把文件生成误写成已经发布。

## 标题来源与约束

- 中文标题来自 `manifest.json.release_name`，英文标题来自 `locales/en/manifest-localization.json.release_name`。
- 标题必须为非空字符串；空白、前后空格、控制或格式字符、过长值及泛化占位标题均失败关闭。
- 长度上限为中文 30 个 code points、英文 80 个 code points、组合标题 125 个 code points 或 200 个 UTF-8 bytes；Unicode `Cc`、`Cf`、`Cs` 类别字符拒绝。
- 工作流先将标题写入 job output，再通过环境变量传给创建步骤，避免直接 shell 表达式插值。
- 标签流程仅创建 Draft Release；已有 Release 不覆盖，资产、校验和、见证与 provenance 按既有机制核验。

## 触发与门禁

- 手动运行 `Release Candidate and Provenance` 只构建并证明当前清单版本，不创建 Release 页面。
- 推送 `vX.Y.Z` 标签时，标签必须与 `manifest.json` 及 Plugin 清单版本完全一致，否则失败关闭。
- Windows 与 Ubuntu 均执行双语覆盖、全仓库链接和完整包验证；发行包在 Windows 上进行两次字节级一致构建。
- GitHub 对中文和英文 ZIP 生成签名来源证明，并保存构建见证、校验和与证明包。
- 标签流程最多创建一个 **Draft Release**。既有 Release 不会被覆盖，自动化也不会公开发布草稿。

## 验证下载产物

下载 ZIP 后，使用 GitHub CLI 按仓库身份验证实际文件摘要及其来源证明：

```shell
gh attestation verify Codex-Skills-V7.4.6-zh-CN.zip --repo OWNER/REPOSITORY
gh attestation verify Codex-Skills-V7.4.6-en.zip --repo OWNER/REPOSITORY
```

将 `OWNER/REPOSITORY` 替换为下载页面显示的仓库身份。`SHA256SUMS.txt` 用于摘要核对，`witness-*.json` 证明同一提交的两次干净构建字节一致，GitHub attestation 则把 ZIP 摘要关联到产生它的工作流身份。三者用途不同，不能互相冒充。

V7.4.6 示例标题：`V7.4.6 | Codex CLI 0.153.4 稳定版兼容 / Codex CLI 0.153.4 stable compatibility`；实际标题以清单字段读回为准。

## 发布新版本

1. 更新清单、Plugin 版本、发行说明、测试和双语文件。
2. 在分支上完成 CI 与人工核验。
3. 创建并推送与清单一致的版本标签。
4. 等待来源证明与草稿 Release 创建成功。
5. 人工检查草稿中的版本、双语 ZIP、见证、校验和与来源证明，再决定是否公开。

## 失败处置与回滚边界

- **CI 失败且尚无 Draft**：保持 Release 未创建，先定位失败门禁；需要改源码时使用新的提交与补丁版本，不盲目重跑，也不自动移动远端标签。
- **Draft 标题、正文或资产错误**：保持 Draft，不公开、不使用 `--clobber`。只修正可审计的元数据；资产或来源提交错误时停止流程，由维护者明确批准删除草稿或改发新补丁版本。
- **标签指向错误提交**：自动化不得强推、删除或重建标签。若标签尚未形成 Release，维护者可在核对保护规则和影响后另行授权修正；默认选择新版本。已经关联公开 Release 的标签不得重定向。
- **Release 已公开后发现问题**：不自动撤回，不静默替换二进制资产。优先发布修复版本并在原 Release 添加更正说明；任何元数据修正、撤回或删除都需要单独授权和操作前后读回。

失败处置必须继续区分 commit、push、tag、CI、Draft、public Release 和安装生效状态；任何一步失败都不能把后续状态写成完成。

历史 Release 标题回填是独立的线上元数据操作，不由上述 Draft-only 流程自动完成。v7.3.0 至 v7.4.3 已完成并逐个线上读回；v7.2.0 及更早未改。

工作流不会上传历史原始 ZIP，不会自动替换既有附件，也不会绕过人工发布确认。

检查清单还需确认标题来源与约束、job output/环境变量传递、Draft-only、既有 Release 不覆盖、双语资产与 provenance、Codex CLI 0.153.4 兼容边界，以及历史标题回填的独立授权和线上读回。
