# 安全策略

English: [SECURITY.en.md](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/blob/main/.github/SECURITY.en.md)

## 支持范围

| 版本 | 状态 |
| --- | --- |
| 7.2.0 | 当前维护 |
| 7.1.0 及更早版本 | 仅保留历史证据，优先升级 |

## 漏洞报告

安全问题请通过仓库的 [Private vulnerability reporting](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/security/advisories/new) 私密提交。公开 Issue、Pull Request、讨论区和提交记录不适合承载漏洞细节、凭据、Token、Cookie、私有路径或其他敏感信息。

报告宜包含：

- 受影响版本和平台；
- 可复现的最小步骤；
- 影响范围与可能的攻击条件；
- 已尝试的缓解方式；
- 经过脱敏的日志或证据。

收到报告后，将先确认影响范围和复现条件，再协调修复、验证与披露节奏。修复尚未公开前，请保留相关细节的私密性。

## 凭据与隐私

- 不提交真实 Token、Cookie、API Key、密码、私钥或环境文件。
- 截图、日志和事件样本应先脱敏。
- Hook 默认只保留最小结构化元数据，不保存原始 Prompt、完整回答、代码正文或 Diff。
- 疑似泄露的凭据应立即在原提供方轮换；从 Git 历史删除文本不能替代轮换。

本策略不承诺特定响应时限，但会按影响与可利用性排序处理。
