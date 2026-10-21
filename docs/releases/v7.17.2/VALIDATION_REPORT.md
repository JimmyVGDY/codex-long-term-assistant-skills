# V7.17.2 验证报告

发行标签绑定提交 `d160b0512ffa359c7a8b52ad59eb8424a2642a7f`。[PR CI](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/actions/runs/39588208484) 和[同提交主分支 CI](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/actions/runs/39598793203) 均已完成并成功；PR 虚拟合并提交、修复提交和标签提交的 Git 文件树完全一致。

定向验证通过：18 项来源恢复、4 项账户路径、2 项安装恢复、19 项原任务范围及 15 项上下文输入测试。文档、安装诊断、统一入口、兼容及交付组运行 86 项（跳过 1 项），另有 7 项发行测试通过。双语覆盖、链接、文档投影、语义检查和两项独立逻辑只读复审通过。

[标签发行验证](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/actions/runs/39598823547) 每组发现并执行 1,384 项主包测试和 265 项运行库测试。下表为各组最终实际结果，跳过项单列，最终无失败或错误。

| 平台 / Python | 主包通过 / 跳过 | 运行库通过 / 跳过 |
| --- | --- | --- |
| Windows / 3.11，第二次运行 | 1,382 / 2 | 265 / 0 |
| Windows / 3.13 | 1,383 / 1 | 265 / 0 |
| Ubuntu / 3.11 | 1,340 / 44 | 259 / 6 |
| Ubuntu / 3.13 | 1,340 / 44 | 259 / 6 |

首次 Windows / 3.11 运行的既有 `test_corrupt_auxiliary_record_does_not_starve_valid_reconciliation` 用例失败。该实现链路未修改，同提交主分支 CI 和本地 13 次隔离运行均通过，因此仅对失败作业进行一次同源码重试并通过。现有 250 毫秒处理窗口可能受运行器延迟影响，具体首次断言原因未获记录，不能认定根因。失败记录未删除，未放宽断言或跳过检查。

公开核验时，重试作业的全部步骤（含 Complete job）、完整测试日志、构建及草稿作业均成功，但该作业及发行运行的 GitHub 汇总仍显示 `in_progress`。这项状态差异单独保留，没有伪造汇总通过。发布依据包括已正式成功的同提交完整 CI、实际发行验证日志及下述制品证据。

2026-10-21 15:05:43 UTC，[正式 Release](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/releases/tag/v7.17.2) 已公开。六个附件全部匿名下载，大小及 SHA-256 与已验证草稿一致；中文和英文 ZIP 的双次构建字节一致，GitHub attestation 绑定本仓库、发行工作流、`refs/tags/v7.17.2` 和上述精确提交。

- 中文 ZIP SHA-256：`14ee2f07c8b32cd3b73f84ce1a615c825093996eab2adcbe9f541e673c86bd75`。
- 英文 ZIP SHA-256：`fa35b35b885921658daf412b337f7bcac7992bde11f9cd1233ad94f31b653452`。

本机安装诊断为 PASS，350 个载荷文件与正式中文包一致；当前 Desktop 会话完成真实父 Hook 来源定位读回。未重启 Desktop，未把定位读回解释为预算强制或系统级只读隔离。已公开标签和资产保持原始内容；本报告在发布后回填。
