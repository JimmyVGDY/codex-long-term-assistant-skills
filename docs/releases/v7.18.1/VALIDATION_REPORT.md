# V7.18.1 验证报告

固定使用 Windows x64 与 Ubuntu 24.04 x64 均可安装的 Python 3.13.17，PR 阶段即核验两端的发行解释器。 [前一标签运行](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/actions/runs/44673559113)

版本定稿前，运行时修复候选在 Windows 与 Ubuntu（WSL）各执行 1,716 项回归，分别通过 1,705 和 1,665 项，其余按环境跳过。Windows 日常账户的新会话已核验 10 个技能、12 条项目 Hook。GPT-6.2 Sol 和 Astra 的 medium 档曾完成真实子任务，账本分别结算 4 和 8 个规划单位。

发布流程随后在两端使用 Python 3.13.9 各通过 48 项相关测试。两种语言均在两个系统双次构建并比对一致。草稿首次创建、重跑、附件替换、缺件、错误说明和查询失败通过本地接口演练。

以上为定稿前的候选证据。正式标签的托管验证、签名和公开附件以对应 GitHub Actions 和 Release 的发布后读回为准。
