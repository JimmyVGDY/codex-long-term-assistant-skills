# Release 自动化与制品来源证明

English: [RELEASE_AUTOMATION.en.md](RELEASE_AUTOMATION.en.md)

## 目标

发行工作流把“源码验证、可复现构建、来源证明、Release 页面公开”拆成不同事实，防止把文件生成误写成已经发布。

## 触发与门禁

- 手动运行 `Release Candidate and Provenance` 只构建并证明当前清单版本，不创建 Release 页面。
- 推送 `vX.Y.Z` 标签时，标签必须与 `manifest.json` 及 Plugin 清单版本完全一致，否则失败关闭。
- Windows 与 Ubuntu 均执行双语覆盖、全仓库链接和完整包验证；发行包在 Windows 上进行两次字节级一致构建。
- GitHub 对中文和英文 ZIP 生成签名来源证明，并保存构建见证、校验和与证明包。
- 标签流程最多创建一个 **Draft Release**。既有 Release 不会被覆盖，自动化也不会公开发布草稿。

## 验证下载产物

下载 ZIP 后，使用 GitHub CLI 按仓库身份验证实际文件摘要及其来源证明：

```shell
gh attestation verify Codex-Skills-V7.3.0-zh-CN.zip --repo OWNER/REPOSITORY
gh attestation verify Codex-Skills-V7.3.0-en.zip --repo OWNER/REPOSITORY
```

将 `OWNER/REPOSITORY` 替换为下载页面显示的仓库身份。`SHA256SUMS.txt` 用于摘要核对，`witness-*.json` 证明同一提交的两次干净构建字节一致，GitHub attestation 则把 ZIP 摘要关联到产生它的工作流身份。三者用途不同，不能互相冒充。

## 发布新版本

1. 更新清单、Plugin 版本、发行说明、测试和双语文件。
2. 在分支上完成 CI 与人工核验。
3. 创建并推送与清单一致的版本标签。
4. 等待来源证明与草稿 Release 创建成功。
5. 人工检查草稿中的版本、双语 ZIP、见证、校验和与来源证明，再决定是否公开。

工作流不会上传历史原始 ZIP，不会自动替换既有附件，也不会绕过人工发布确认。
