<p align="right">
  <strong>简体中文</strong> · <a href="README.en.md">English</a>
</p>

# Codex 跨项目长期技术助手

<p align="center">
  <img src="docs/assets/social-preview.jpg" alt="Codex 跨项目长期技术助手双语项目预览" width="100%">
</p>

<p align="center">
  面向 Codex 的跨项目工程协作框架：Skill 路由、多 Agent 独立复审、可恢复任务记忆、生命周期事件与受控演进。
</p>

<p align="center">
  <a href="https://github.com/JimmyVGDY/codex-long-term-assistant-skills/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/JimmyVGDY/codex-long-term-assistant-skills/actions/workflows/ci.yml/badge.svg"></a>
  <a href="https://jimmyvgdy.github.io/codex-long-term-assistant-skills/"><img alt="双语文档站" src="https://img.shields.io/badge/docs-%E4%B8%AD%E6%96%87%20%7C%20English-00b8a9"></a>
  <a href="https://github.com/JimmyVGDY/codex-long-term-assistant-skills/releases/latest"><img alt="Latest release" src="https://img.shields.io/github/v/release/JimmyVGDY/codex-long-term-assistant-skills"></a>
  <a href="LICENSE"><img alt="Apache-2.0" src="https://img.shields.io/github/license/JimmyVGDY/codex-long-term-assistant-skills"></a>
  <img alt="Python 3.11+" src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white">
  <img alt="Codex CLI 0.153.2" src="https://img.shields.io/badge/Codex%20CLI-0.153.2-111827">
</p>

V7.4.3 基于 Codex CLI 0.153.2 的稳定兼容窗口收紧模型身份隐私边界：Reviewer、Explorer、Worker 只按派发前批准档位和预留单位治理，运行后不读取、推断或保存宿主实际模型身份。旧版 Event V2 与 Budget V1 链保持只读验签能力，但只能通过安全投影进入新聚合。

**快速入口：** [双语文档站](https://jimmyvgdy.github.io/codex-long-term-assistant-skills/) · [下载](#下载) · [使用示例](#可复现使用示例) · [兼容矩阵](#兼容矩阵) · [安装](#五分钟升级) · [文档](#文档与协作)

## 下载

| 发行包 | 适用界面 | 下载 |
| --- | --- | --- |
| `Codex-Skills-V7.4.3-zh-CN.zip` | 简体中文 | [下载中文安装包](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/releases/download/v7.4.3/Codex-Skills-V7.4.3-zh-CN.zip) |
| `Codex-Skills-V7.4.3-en.zip` | English | [Download English package](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/releases/download/v7.4.3/Codex-Skills-V7.4.3-en.zip) |

[查看最新 Release、校验和与构建见证](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/releases/latest)

## 核心能力

- 10 个工程 Skill，按当前任务最小充分路由并渐进加载。
- 4 个稳定主领域：通用后端、通用前端、通用 AI、数据中间件基础设施；语言和框架作为按需 Reference。
- 7 个逻辑只读 Reviewer，定义文件不写死模型或推理强度。
- 6 个生命周期 Hook：`UserPromptSubmit`、`PreToolUse`、`SubagentStart`、`SubagentStop`、`Stop`、`SessionEnd`。
- TaskOutcomeEvent 3.0、`project_id + repo_fingerprint` 双重隔离与独立连续哈希链。
- 可恢复检查点、延迟 SessionEnd 封印、事件归档与跨项目健康概览。
- 包级路由回归与真实宿主路由验收分层记录；宿主证据绑定原始最终报告的 SHA-256。
- 演进候选按信号类型分别检查所需证据，不再因无关遥测缺失而全局阻断。
- `execution_authorization=NONE` 的受控优化提案，不授予实施权限。

```mermaid
flowchart LR
    A[任务输入] --> B[Skill 最小路由]
    B --> C[主 Agent 执行]
    C --> D[独立 Reviewer]
    C --> E[生命周期 Hooks]
    D --> E
    E --> F[TaskOutcomeEvent 3.0]
    F --> G[项目隔离与哈希链]
    G --> H[Snapshot / Assessment / Proposal]
    H --> I[人工决策]
```

## 可复现使用示例

以下内容展示一次典型只读任务的输入、流程和可检查结果；它是使用示例，不是当前会话的运行证明。

**任务输入**

```text
检查当前仓库的安装器升级路径，只读分析，不修改文件；
按风险选择 Reviewer，并区分已确认事实、推断和未验证项。
```

**预期流程**

```text
任务输入
  -> 路由 engineering-quality-delivery
  -> 读取安装器、清单、测试与升级文档
  -> 按实际风险启动逻辑只读 Reviewer
  -> 汇总并去重 Reviewer 发现
  -> 输出证据、风险和未验证边界
```

生命周期可形成 `TURN_OPENED -> SUBAGENT_STARTED -> SUBAGENT_STOPPED -> TASK_COMPLETED` 事件序列；会话结束后由 `SessionEnd` 进入延迟封印流程。V7.4.3 只证明派发前策略符合批准档位与 Terra High 上限，不读取、不推断、不保存或导出宿主实际使用的模型与推理强度。

## 兼容矩阵

| 环境或模式 | 当前定位 | 已有验证层级 | 边界 |
| --- | --- | --- | --- |
| Windows 原生 Codex CLI 0.153.2 + Plugin | 实机锚点 | V7.4.3 账户级事务重装、Plugin 读回与父子生命周期封印通过 | 宿主模型身份不属于验收信息；实际卸载/回滚仍仅有隔离测试证据 |
| Windows + 11 个固定 Codex 稳定版 | 本地隔离矩阵 | CLI、Plugin 往返、合成 Hook 与官方制品校验逐版通过 | 不等于真实账户会话 |
| Windows / Ubuntu GitHub 矩阵 | 发布门禁 | 11 个稳定版逐版重放 | CI 尚须在候选提交上读回 |
| standalone 模式 | 显式兼容模式 | 安装结构与回归测试覆盖 | 不宣称 Plugin 宿主兼容 |
| macOS | 未验证 | 无当前 CI 或宿主验收证据 | 状态保持 `UNVERIFIED` |

Python 最低版本为 3.11；公开 CI 在 Windows 与 Ubuntu 上同时验证 3.11 和 3.13。其他环境组合应先执行 `doctor`、`dry-run` 和 `verify`，再判断可用状态。

V7.4.3 的冻结窗口为 `0.153.2`、`0.153.1`、`0.153.0`、`0.152.1`、`0.152.0`、`0.151.0`、`0.150.1`、`0.150.0`、`0.149.1`、`0.149.0`、`0.148.0`。补丁版本独立计数；未来版、预发布版和其他窗口外版本不自动接纳。

## 五分钟升级

1. 下载对应语言的 ZIP，并解压到临时目录。
2. 在解压后的包根目录依次执行：

```powershell
python scripts\package_manager.py doctor
python scripts\package_manager.py install --scope user --mode plugin --dry-run
python scripts\package_manager.py install --scope user --mode plugin
python scripts\package_manager.py verify --scope user --mode plugin
codex plugin list --json
```

3. 仅当 Plugin 读回 `installed=true`、`enabled=true`、`version=7.4.3`，schema 3 宿主状态为 `HOST_COMPATIBLE`，且旧领域 Skill 不再发现时，升级状态才成立。

安装器会识别已有版本、备份并移除受管旧 Skill、拒绝链接与 Reparse Point 风险，并保留未知文件。完整流程见 [安装与恢复](docs/INSTALLATION_RECOVERY.md) 和 [V7.4 使用指南](docs/USER_GUIDE_V7.4.md)。

## 派发策略与模型身份隐私边界

Agent 只使用批准派发档位、permit 引用与预留成本治理子任务；宿主实际模型身份和推理强度不纳入事件、预算、Reviewer、Evolution 或发布证明。自动成本阶梯为：

```text
luna-low -> luna-medium -> terra-medium -> terra-high
```

自动流程拒绝 Sol、`xhigh`、`max`、`ultra` 及任何超过 `gpt-5.6-terra + high` 的配置。

## 文档与协作

- [文档中心](docs/README.md)：安装、配置、架构、模型策略、验证与历史资料。
- [贡献指南](.github/CONTRIBUTING.md)：分支、提交、双语覆盖与验证方式。
- [安全策略](.github/SECURITY.md)：漏洞报告边界与敏感信息处理。
- [行为准则](.github/CODE_OF_CONDUCT.md)：公共协作的基本边界。
- [版本记录](CHANGELOG.md) · [V7.4.3 发行说明](docs/releases/v7.4.3/RELEASE_NOTES.md)

## 本地验证

```powershell
python scripts\localization-audit.py --strict
python scripts\validate-package.py
```

发行构建采用固定时间戳、稳定排序和 SHA-256 见证。源码仓库与发行安装包是不同证据层：仓库 CI 证明当前提交，Release 附件及其见证证明可下载产物。

## 发行来源证明

`Release Candidate and Provenance` 工作流会校验版本标签、在 Windows 与 Ubuntu 上验证源码、构建两个可复现 ZIP，并通过 GitHub Artifact Attestations 为实际 ZIP 摘要生成签名来源证明。标签流程只创建草稿，不会自动公开发布或覆盖既有 Release。

```shell
gh attestation verify Codex-Skills-V7.4.3-zh-CN.zip --repo OWNER/REPOSITORY
```

完整门禁和新版本发布步骤见 [Release 自动化与制品来源证明](docs/releases/RELEASE_AUTOMATION.md)。

## 安全边界

- 不自动修改 Skill、Reviewer、模型路由、全局配置或业务仓库。
- 不自动接受或执行优化提案。
- 不自动提交、推送、部署、重启、操作生产环境或写入业务数据。
- Evidence 只记录事实，不授予权限。
- 默认不保存原始 Prompt、完整回答、代码正文、Diff、Token、Cookie、API Key 或凭据。

Apache-2.0 许可，见 [LICENSE](LICENSE)。
