# V7.18.1 验证报告

正式版已于 2026-11-20 10:51:37 UTC 公开，标签绑定提交 `4f905b823ef2d2932006616e618d7f888100639a`。 [GitHub Release](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/releases/tag/v7.18.1)

PR 保护检查和标签发行任务均已通过。Windows 与 Ubuntu 在同一 Python 补丁版本构建双语 ZIP，并通过签署前的跨平台比对。 [PR 检查](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/actions/runs/44683838094) · [标签运行](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/actions/runs/44693161013)

正式标签首轮的 Windows 3.11 有一项迟到回执回归失败。同一提交的主分支检查通过该项，Windows 本机连续 12 次通过。人为延迟读取 300 毫秒后，首次处理推迟，下一次回调准确结算一次。托管日志只记录用例结果，未给出该次断言详情。随后沿用原标签，仅重跑失败作业与其下游。 [首次失败](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/actions/runs/44693161013/job/136143771873) · [同提交主分支检查](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/actions/runs/44693136099/job/136143480336)

第二轮通过了迟到回执测试，另一项 Node 权限拒绝用例的子进程超过 10 秒时限，作业记录为 TimeoutExpired。该用例在首轮以及同提交主分支均通过，两项原始用例在本机 Windows Python 3.11.18 和 3.12.14 各交替运行 12 轮，均全部通过。第三轮在原标签上重跑该 Windows 作业并开启详细日志。 [第二次作业](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/actions/runs/44693161013/job/136173743661)

| 平台与 Python | 主包通过 / 跳过 | 运行时通过 / 跳过 |
| --- | ---: | ---: |
| ubuntu-latest, Python 3.11 | 1408 / 45 | 260 / 6 |
| ubuntu-latest, Python 3.13 | 1408 / 45 | 260 / 6 |
| windows-latest, Python 3.11 | 1450 / 3 | 266 / 0 |
| windows-latest, Python 3.13 | 1451 / 2 | 266 / 0 |

六个公开附件已逐项匿名下载并核对 SHA-256。

| 附件 | SHA-256 |
| --- | --- |
| `Codex-Skills-V7.18.1-en.zip` | `39f890705e6ded6b44428d276c96dea4fd7141d74814ce4990e880bd2b18e678` |
| `Codex-Skills-V7.18.1-provenance.json` | `f446d7557134516d4f9e49fd1de8485e854f9749fcff89b8ccc643e5572551b7` |
| `Codex-Skills-V7.18.1-zh-CN.zip` | `44c76242d8f7ccba639557958094e57feae4e28223d3896271ec2c69c3f407c3` |
| `SHA256SUMS.txt` | `dcf56e780857ea49368ff0181baa2e8a8844edef6a0ea7e8f63612d17b7f2c29` |
| `witness-en.json` | `b43adbd1457020d0c69a4a08f4fbec992c0fe50b28566e8774fc277917f46bcf` |
| `witness-zh-CN.json` | `e4d62e2071dc11a4d4dbd77facd4b443960f4e3b7381040f58d26dec79846441` |

## 定稿前验证

固定使用 Windows x64 与 Ubuntu 24.04 x64 均可安装的 Python 3.13.17，PR 阶段即核验两端的发行解释器。 [前一标签运行](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/actions/runs/44673559113)

版本定稿前，运行时修复候选在 Windows 与 Ubuntu（WSL）各执行 1,716 项回归，分别通过 1,705 和 1,665 项，其余按环境跳过。Windows 日常账户的新会话已核验 10 个技能、12 条项目 Hook。GPT-6.2 Sol 和 Astra 的 medium 档曾完成真实子任务，账本分别结算 4 和 8 个规划单位。

发布流程随后在两端使用 Python 3.13.9 各通过 48 项相关测试。两种语言均在两个系统双次构建并比对一致。草稿首次创建、重跑、附件替换、缺件、错误说明和查询失败通过本地接口演练。
