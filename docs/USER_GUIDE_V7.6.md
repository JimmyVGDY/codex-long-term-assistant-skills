<!-- Generated compatibility copy from docs/USER_GUIDE.md; edit that source and run scripts/documentation.py sync. -->

[当前入口](USER_GUIDE.md)

# Codex 跨项目长期技术助手 V7.13.0 使用说明

## 快速开始

在解压后的 V7.12.0 包中，Windows 运行 `./scripts/install-base.ps1`，POSIX 运行 `./scripts/install-base.sh`，随后直接描述工程任务。基础 Plugin 加载十个 Skill，无需本包 Python runtime 或 API Key，不安装账户 Hook、Reviewer、全局规则或长期运行时状态。

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

参数与启停方法见[能力索引](CAPABILITY_INDEX.md)链接的完整流程。下面的委派预算是按任务单独启用的另一项控制。

## 1. 委派预算与隐私边界

Reviewer、Explorer、Worker 共用根任务预算，控制器不重复扣费。新任务采用 DelegationBudget V3、Reviewer 状态 V8、结果 V5；旧任务固定原策略。主 Agent 保持当前选择。Worker/Explorer 仍使用原四组合；登记 Reviewer 从 Luna Low 的基础 1 分开始，按复审预算模式和有效证据加分，算完后一次选择十组合之一，最高 Astra High。

代理单位不是实际价格或模型能力排名。完整组合、证据去重、质量约束、扩展额度和家族次数限制见[模型选择与预算](MODEL_ROUTING_AND_COST_POLICY.md)。没有满足质量约束且可负担的组合时停止派发。

## 2. 使用顺序

1. 绑定仓库外 Project Profile，建立采用新评分策略的 Task Envelope，选择 LIGHT、STANDARD 或 STRICT。
2. 在仓库外初始化 V3 账本，使用 `--root-envelope` 和真实宿主 session 绑定。旧任务显式选择 `--policy-id four-tier-v1`；不能把旧信封静默解释成新策略。
3. 每次先决定 INLINE 或 DELEGATE。Reviewer 的 `decide` 输入为 `--selection-input`、`--review-assignment` 与根信封；提交证据引用及路径，不提交计算结果。程序从 Luna 起算并固定最终组合与 permit。
4. V8 控制器关联同一 permit、packet hash 和唯一复审槽位后，按宿主接口使用带 `task_name` 的参数或 `native_request_parameters` 一次派发。原生无任务名接口须将本次返回的 `native_message_prefix` 原样前置于 `message`；缺失、错误或重复消费的引用均拒绝，不按角色猜配许可。Reviewer 组合必须明确指定，不能隐式继承。
5. 启动宿主时设置 `CP_DELEGATION_BUDGET_PATH`、`CP_DELEGATION_ENVELOPE_PATH`、`CP_DELEGATION_BUDGET_REQUIRED=1`。PreToolUse 验证真实根身份、当前基线、角色和 permit 后原子预占。
6. PostToolUse 的工具调用 ID 和 Agent ID 回执与 SubagentStart/Stop 精确关联，允许乱序。V3 的 start/complete CLI 不可替代原生回执。无关联、超时或未知响应保持未完成，不能猜成 PASS 或退款。

增强不会自动为任务建账本。未激活时仅为策略约束；严格预算配置缺失或损坏时拒绝派发。原生未创建响应尚无已核验适配时，不开放自动未启动退款；已启动、失败或取消不退费。

## 3. 重试与切换

缺失证据不构成升级理由。同家族增加强度与跨家族切换分别记录；再次复审绑定前次终态、结果引用与新证据，不能通过改名重新使用许可或重置次数。重试需要明确的新轮次或槽位，并继续受同一个根预算约束。

## 4. 成本与校准

只保存批准组合、评分和成本代理，不读取、推断或保存宿主实际型号。比较样本固定项目、仓库、策略摘要、公式与声明比较对；旧单位不和新公式混算。主协调者带结果与验证引用最终化后才进入回放，样本不足保持 NO_CHANGE。Proposal 永久 `execution_authorization=NONE`。

V1 预算只读；V2 按原字节规则读取和续写；V7/V4 复审保持原语义。新任务使用独立 V3 账本，未知版本失败关闭。安装、注册、Hook 行为、真实派发与实际型号分别是不同证据层，不以模拟测试代替宿主验收。

## 5. Codex 0.154.0 边界

V7.12.0 的 Plugin 窗口是 Codex CLI 0.154.0 与此前十个稳定发行版，精确列表由 `config/codex-compatibility-v1.json` 冻结。本地 Marketplace manifest 必须包含 `interface.displayName`；未来版、预发布版和其他窗口外版本不会自动接纳。0.154.0 修复 Astra 在内置模型选择器中的可见性，在未显式配置模型时将其设为内置默认，并把异步提问说明约束为仅在相关工具可用时适用；这些变化不修改本包已冻结的 Plugin/Hook 合同。Worker/Explorer 仍限原 Luna/Terra 四档；登记 Reviewer 按证据预算从 Luna 起算，最高 Astra High。

基础安装必须读回 `installed=true`、`enabled=true`、`version=7.12.0`、十个 Skill 与空 Plugin Hook 清单；增强安装还须核验 `HOST_COMPATIBLE` schema 3 快照、账户 Hook 和受管运行时资产。磁盘已有文件不等于 Plugin 已注册或已启用。

## 任务反馈与优化收益

沿用 V7.5 引入的验证反馈、观察健康门禁、显式启用的增量分析、逐账本场景校准、可检验假设和收益验证关闭；V7.6.2 不再从异步 UserPromptSubmit 注入绑定，身份改由当前仓库外执行信封显式提供。按[受控演进操作手册](evolution/CONTROLLED_EVOLUTION_OPERATIONS.md)执行；项目自动化默认关闭。

## 能力复用与可选门禁

通过[能力索引](CAPABILITY_INDEX.md)完成有界初扫与增量更新，复用前核对候选源码、业务适用性与维护成本。项目门禁默认关闭；V7.12.0 只在显式启用策略下把规范 `apply_patch` 接入 Operation v2：A 创建起点并拒绝，准备后由不同 B 领取许可，匹配的 PostToolUse 回执后才能完成核验。旧 GateTask 永不转换为新许可。参见[验收规程](COMPONENT_REUSE_ACCEPTANCE.md)和[发行验证](releases/v7.12.0/VALIDATION_REPORT.md)。
