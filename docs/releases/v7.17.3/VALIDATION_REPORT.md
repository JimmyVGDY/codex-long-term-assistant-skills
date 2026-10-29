# V7.17.3 验证报告

[正式 Release](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/releases/tag/v7.17.3) 已于 2026-10-29 13:37:22 UTC 公开，非草稿、非预发布，绑定提交 `1255fb0d18bc8b4e1ab580ca666a880aee15cdf3`。

[PR CI](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/actions/runs/40856993519)、[同提交主分支 CI](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/actions/runs/40867919490) 以及[标签发行验证](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/actions/runs/40868175634) 均完成并成功。PR 的测试合并提交、源码分支和正式 squash 提交的 Git 文件树相同。下表为标签发行中各组实际结果；每组记录 1,427 项主包测试与 265 项运行库测试，跳过单列，无失败或错误。

| 平台 / Python | 主包通过 / 跳过 | 运行库通过 / 跳过 |
| --- | --- | --- |
| windows-latest / 3.11 | 1425 / 2 | 265 / 0 |
| windows-latest / 3.13 | 1426 / 1 | 265 / 0 |
| ubuntu-latest / 3.11 | 1382 / 45 | 259 / 6 |
| ubuntu-latest / 3.13 | 1382 / 45 | 259 / 6 |

当前版本另有 70 项定向检查通过；修正英文 Plugin 覆盖版本遗漏后，受影响的完整双语发行模块 20 项通过。版本化前同一适配实现的 115 项相关回归及来源并发场景 20 次重复运行另行保留，不把重叠用例相加。双语、文档投影和 1,806 条仓库链接检查通过。早期候选的过期窗口夹具失败、本轮英文覆盖遗漏及旧 CI 取消记录均保留；修复后重新完成上述完整矩阵。

六个实际附件已匿名下载，大小和 SHA-256 与核验过的草稿及公开 API 摘要一致。中英文 ZIP 与本地双次构建、PR CI 构建及正式签署产物字节一致，均为 958 个条目。GitHub attestation 通过本仓库、发行工作流、`refs/tags/v7.17.3` 和精确提交 `1255fb0d18bc8b4e1ab580ca666a880aee15cdf3` 的约束验证。说明正文从 Release API 读回，不作为第七个附件。

- 中文 ZIP SHA-256：`bb40cfb2a7927deb983ffd6b546ca009b498022df5019540c4edb20762484d28`。
- 英文 ZIP SHA-256：`9126ac816f894f5b2b991f13f1cf07e560cc40bb4f6f68cb9a19bb56d8ea77b5`。

真实 Desktop 验收来自版本化前已安装的修改候选，目标为 26.1023.50603 / build 22391、内部组件 0.165.0-alpha.1.2，覆盖原生读取、人工追加恢复、原账本结算、运行中回合取消和重复回收幂等。密文直接续跑保持拒绝，实际采用同工作、同根和原批准额度内的新调用安全回退；UNKNOWN 与 CANCELLED 原值保留。未把包测试或构建工具版本当成真实桌面运行验收。

此前实际回滚中，25 个受管目标和 350 个旧载荷文件字节一致，59 个派生字节码缺失单列保留；最终修复候选未重做整轮回滚。当前账户仍为已验收的 7.17.2 修改候选，正式 7.17.3 未另行安装，本轮未执行 Desktop 重启，也未验收重启后的更新客户端。已公开标签与附件保留发行时字节，本报告在发布后的 Git 文档中回填。
