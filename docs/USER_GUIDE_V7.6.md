<!-- Generated compatibility copy from docs/USER_GUIDE.md; edit that source and run scripts/documentation.py sync. -->

[当前入口](USER_GUIDE.md)

# Codex 跨项目长期技术助手 V7.15.3 使用说明

## 快速开始

在解压后的 V7.15.3 包中，Windows 运行 `./scripts/install-base.ps1`，POSIX 运行 `./scripts/install-base.sh`，随后直接描述工程任务。基础 Plugin 加载十个 Skill，无需本包 Python runtime 或 API Key，不安装账户 Hook、Reviewer、全局规则或长期运行时状态。

简单局部任务默认由主 Agent 完成；Profile、索引、全扫和预算台账不是开始任务的前提。需要时再通过 `install-user` 接入增强，详见[安装与恢复](operations/INSTALLATION_RECOVERY.md)。下方索引、Hook 与预算步骤适用于增强能力；严格预算仅在真实宿主绑定、账本和 dispatch permit 均可核验时强制执行，否则模型上限仅为策略约束。

## 四条日常路径与统一入口

新使用者可以从四条路径开始：修 Bug、做功能、审查、继续任务。解压包内的 `scripts/cp-assistant.ps1`、`scripts/cp-assistant.sh` 和 `scripts/cp-assistant.py` 使用白名单转发到现有安装器与 runtime；旧 `package_manager.py`、`cp-runtime.py` 和基础安装入口继续保留。

| 路径 | 请求示例 | 需要知道的边界 |
| --- | --- | --- |
| 修 Bug | “修复失败验证并运行最小相关测试” | 先让 Agent 读取当前代码和定向测试，不需要先安装增强。 |
| 做功能 | “实现这个功能，按风险执行验证” | 只有需要长期状态、Hook、Reviewer、预算或受控写入时才安装增强。 |
| 审查 | “审查当前分支的兼容、安全和回滚风险” | Reviewer 是否启动由风险和独立证据需要决定，不由入口强制。 |
| 继续任务 | “继续上次任务，告诉我做到哪里和下一步” | 使用只读 `resume` 查看阶段、检查点、仓库变化和需重验项。 |

统一入口示例：

```powershell
.\scripts\cp-assistant.ps1 help
.\scripts\cp-assistant.ps1 install-base
.\scripts\cp-assistant.ps1 status
.\scripts\cp-assistant.ps1 doctor
.\scripts\cp-assistant.ps1 inventory --scope user --mode plugin --json
.\scripts\cp-assistant.ps1 resume --repo-path E:\work\repo --profile C:\safe-state\project-profile.json --checkpoint-dir C:\safe-state\task
.\scripts\cp-assistant.ps1 recover --scope user
```

`status`、`doctor`、`inventory`、`verify` 和 `resume` 是查询或验证动作；`install-base`、`install-enhancement` 和 `recover` 会改变受管状态。查询不会自动安装、初始化 Profile、刷新索引、修复账本或调用安装恢复。`resume` 支持两种形式：绑定 `--profile`（可同时提供 `--state` 与一个或多个 `--evidence`），或只提供明确的 `--checkpoint-dir` 读取旧 Markdown 检查点。缺少输入、证据过期、预算耗尽或仓库变化会保留 `UNKNOWN/PARTIAL/STALE`，不会伪造当前通过。

统一入口只承诺实际存在的参数。`verify` 不接受不存在的 `--json`；需要机器 JSON 时使用 `status --json`、`doctor --json`、`inventory --json` 或 `resume --json`。无 Python 时，`help` 和 `install-base` 仍可运行，其他管理命令返回明确的依赖缺失结构，并提示使用 `codex plugin list --json` 做原生读回。

## 体验基准

`scripts/ux-benchmark.py` 只在显式调用时执行确定性命令采样，不启动模型、不上传数据、不保存 Prompt 或完整输出。`collect`、`import-observations` 和 `compare` 的输入、输出和隐私字段见 `tests/fixtures/ux-benchmark/protocol.json`。包装层耗时或工具数变化只能说明测量样本的变化，不能单独证明真实 Agent 任务提速。

`status` 与 `doctor` 可通过 `--profile <项目Profile> --repo-path <仓库>` 读取显式项目的控制准备条件。已启用门禁但运行时不可用会阻断对应能力；没有实际操作许可时不宣称受控写入可执行。`inventory` 在文件不可读或状态损坏时返回明确结果，不修复或删除资产。

基准命令可使用 `--command-file <JSON参数数组文件>` 避免 Shell 引号问题。输出必须是包根目录外的新文件；比较时重新计算统计，核对完整来源 SHA、fixture、场景及环境。少于 20 个有效耗时样本不输出 p95。

## 组件复用的使用顺序

1. 核验仓库根、Project Profile、已有外部索引和当前覆盖；索引是定位线索，源码与契约决定适用性。
2. 首次公共能力开发按当前范围执行有界初扫，预算耗尽时记录待续扫部分；后续先查询候选，再阅读源码、使用方和测试。
3. 比较语义、权限、契约、状态、依赖、性能、测试/回退及维护成本，选择 reuse、extend、extract 或 independent。
4. 需要门禁时显式 enable 并 status 读回；在实际加载 Hook 的新任务中依次 prepare、开发验证、finish、check。门禁启用本身不建立索引，也不等于已执行。
5. 对变更源文件和实际采用的过期候选做限定更新；新增公共能力登记定位，迁移保留 ID。无变化或无关任务不重复扫描。
6. PARTIAL、BLOCKED、FAILED、CANCELLED 保留原含义；禁用保留索引与历史回执。流程 PASS 不能代替业务语义与兼容验证。

参数与启停方法见[能力索引](CAPABILITY_INDEX.md)链接的完整流程。下方预算由增强运行时按根任务管理，基础Plugin不冒称强制预算已生效。

## 1. 委派预算与隐私边界

Reviewer、Explorer、Worker共用根任务预算。增强运行时的新默认`desktop-g6-deterministic-v1`使用GPT-6九档，信息不足使用Sol/medium，不要求统计资格。主Agent保持当前选择，旧根固定原策略和费用语义。

脚本计算事实、选型、预占、必需预留和重试；模型保留语义判断及允许范围内的调整建议，执行最终批准参数。规划单位不是实际价格或能力排名。见[模型选择与预算](MODEL_ROUTING_AND_COST_POLICY.md)。缺证据默认或降级继续；预算不足则排队、调整范围或继续本地工作，不虚构调用。

## 2. 使用顺序

1. 识别项目、任务与已有根策略。新任务按已授权默认模板初始化，旧根原样回放；改策略保留交接、历史费用和迟到事件归属。
2. 从增强运行时的准备入口获取默认组合、允许调整范围、共享预算、门禁状态和下一步；未知事实保持UNKNOWN。
3. 执行脚本精确参数；补读、拆分、调序或改变型号/强度时提交结构化申请，由脚本重算。没有长篇理由或收益卡不阻止默认任务。
4. PreToolUse原子预占，回执和子任务终态按真实身份关联。通用status、超时或取消请求不能变成PASS或退款。
5. 主/子工具、预审、复审、修复和安装采用一致的缺证据规则；继续可逆工作，已确认违规只限制对应动作。平台权限与信任不因此关闭。
6. 基础Plugin仅加载Skill时，不声称存在增强运行时的强制账本或Hook保证；以当前安装读回为准。真实接口不可用时报告限制并继续可行本地工作。

## 3. 重试与切换

按错误类别、根预算和总时限决定重试；运行中或终态不明时查询同一调用。同材料无新信息不反复重跑，必要降档不挤占升档次数；切策略或拆分不清零预算。用户明确指定的型号优先于默认，真实不可用或不可支付时说明具体冲突。

## 4. 成本与校准

批准组合、规划单位与可获得的实际计量分开记录；模型语义建议不冒充已验证事实。自然发生的独立样本可供后续版本校准，样本不足维持当前参数并继续服务，不恢复资格前置。Proposal永久保持`execution_authorization=NONE`。

旧V1/V2/V3/V4账本和结果按冻结合同读取，不重新计费或判定。安装、注册、Hook、真实派发、验证通过和已生效分别读回；合成测试不替代Desktop原生验收。

## 5. Codex 0.162.1 边界

V7.15.3 的内部组件窗口是 Codex CLI 0.162.1 与此前十个稳定发行版，精确列表由 `config/codex-compatibility-v1.json` 冻结；这不建立独立 CLI 产品支持。本地 Marketplace manifest 必须包含 `interface.displayName`；未来版、预发布版和其他窗口外版本不会自动接纳。0.162.0 增加受管 Git worktree、任务固定、转录复制与更多链接交互，并改进自定义 Responses provider、沙箱与 Windows 文件访问；0.162.1 修复多行异步提问崩溃和后台服务 feature 默认不一致导致的启动失败。这些上游变化不自动改变本包的 Reviewer 资格、预算或 Operation v2 合同，也不撤销上文已发布的 GPT-6 脚本决策默认。0.162.x 的 Hook discovery/schema 沿用 0.161.0 合同，但 apply_patch handler 再次漂移，因此使用独立 `result-v162`；context 未漂移。0.161.0 保留 `result-v161`，旧 `0.160.x`、`0.159.x` 及 0.158.0 继续复用 `result-v158`；0.156.1 与 0.156.0 已退出并失败关闭。

基础安装必须读回 `installed=true`、`enabled=true`、`version=7.14.7`、十个 Skill 与空 Plugin Hook 清单；增强安装还须核验 `HOST_COMPATIBLE` schema 3 快照、账户 Hook 和受管运行时资产。磁盘已有文件不等于 Plugin 已注册或已启用。

## 任务反馈与优化收益

沿用 V7.5 引入的验证反馈、观察健康门禁、显式启用的增量分析、逐账本场景校准、可检验假设和收益验证关闭；V7.6.2 不再从异步 UserPromptSubmit 注入绑定，身份改由当前仓库外执行信封显式提供。按[受控演进操作手册](evolution/CONTROLLED_EVOLUTION_OPERATIONS.md)执行；项目自动化默认关闭。

## 能力复用与可选门禁

通过[能力索引](CAPABILITY_INDEX.md)完成有界初扫与增量更新，复用前核对候选源码、业务适用性与维护成本。项目门禁默认关闭；V7.14.6 只在显式启用策略下把规范 `apply_patch` 接入 Operation v2：A 创建起点并拒绝，准备后由不同 B 领取许可，匹配的 PostToolUse 回执后才能完成核验。旧 GateTask 永不转换为新许可。参见[验收规程](COMPONENT_REUSE_ACCEPTANCE.md)和[发行验证](releases/v7.14.6/VALIDATION_REPORT.md)。
