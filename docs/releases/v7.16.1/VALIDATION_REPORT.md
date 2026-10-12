# V7.16.1 验证报告

正式版于 **2026-10-12 16:26:46 UTC（北京时间 2026-10-13 00:26:46）**[公开发布](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/releases/tag/v7.16.1)，绑定提交 `8a355abbbd68af32145364d1b5a7c65985f0baf1`。后续文档同步不改写标签或签名制品。

## CI 与公开制品

[正式发行流水线](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/actions/runs/38269549971)四组完整验证均通过；以下计数来自作业中的结构化报告。

| 平台 | Python | 包测试 | 运行时测试 |
|---|---|---|---|
| Ubuntu | 3.11 | 1,150 通过，42 按条件跳过 | 233 通过，6 按条件跳过 |
| Ubuntu | 3.13 | 1,150 通过，42 按条件跳过 | 233 通过，6 按条件跳过 |
| Windows | 3.11 | 1,190 通过，2 按条件跳过 | 239 通过 |
| Windows | 3.13 | 1,191 通过，1 按条件跳过 | 239 通过 |

[PR CI](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/actions/runs/38260958780)与[主线 CI](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/actions/runs/38269253642)通过。双语可复现包、校验和、构建见证及 GitHub 签名来源验证通过；证明绑定本仓库、上述提交、`refs/tags/v7.16.1` 和正式发行工作流。六个公开附件均经匿名下载核对大小和 SHA-256，与签名候选一致。

## 本机与运行核验

- 修复前，实际 Hook 入口的三个断言稳定失败：2 MiB + 1 字节的主任务执行前、执行后，以及 8 MiB 图片形状结果。
- 修复后，新增边界与对抗用例及既有 V5/G6 定向回归共 52 项通过；受影响发行与完整性测试 25 项通过。
- 本机 Python 3.14 合成测量：8/32 MiB 输入约 0.015/0.057 秒，解析器峰值约 2.2 MiB，不含输入构造；不作为跨机器性能保证。
- 正式中文包受管升级后，安装验证与严格 doctor 通过，版本为 7.16.1，Plugin 已启用且宿主兼容。源包、Marketplace 和缓存的 330 个载荷文件摘要一致。
- 已安装 Hook 的新进程验证主任务超限 PreToolUse/PostToolUse 均返回中性，子任务仍被原有 2 MiB 上限拒绝。真实 `view_image` 工具调用成功返回 4,196,117 字符的图片结果。
- 未执行 Desktop 重启，未重放原项目完整业务链路。

## 保留边界

本机额外 Windows/Python 3.14 完整检查曾出现 7 个 PowerShell 相关失败或错误；定向确认默认 Restricted 策略阻止脚本执行，进程级 RemoteSigned 后同组 7 项全部通过，系统策略未变。后续完整检查仍有 1 项目录重解析点用例 ERROR；该用例单独及强制目录联接回退路径均通过，完整运行异常的原因未取得直接证据。原失败记录保留，没有删除断言或跳过用例。

`RELEASE_COMPLETE` 已由精确提交的 CI、签名制品与公开发行读回证实。`INCIDENT_EFFECTIVE` 仅有本机 Hook 和原生大结果调用的证据，原项目业务验收仍未完成。独立复审范围与限制见[审计报告](AUDIT_REPORT.md)。
