# Codex 跨项目长期技术助手 V7.10 使用说明

## 快速开始

在解压后的 V7.10.0 包中，Windows 运行 `./scripts/install-base.ps1`，POSIX 运行 `./scripts/install-base.sh`，随后直接描述工程任务。基础 Plugin 加载十个 Skill，无需本包 Python runtime 或 API Key，不安装账户 Hook、Reviewer、全局规则或长期运行时状态。

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

增强运行时保留 Reviewer、Explorer、Worker 的同一个根任务加权预算，并把模型身份隐私边界收紧到派发之前。Task Envelope 声明预算档位，`delegation-budget.py` 维护仓库外追加式 Budget V2 账本，PreToolUse Hook 在派发前按批准档位原子预占，Reviewer 控制器只维护复审轮次与 Finding，不再重复计费，也不接收宿主运行时模型身份。

模型权重固定为：`luna-low=1`、`luna-medium=2`、`terra-medium=4`、`terra-high=8`。初始预算为：

| 档位 | 单位 | 派发 | 并行 | 深度 | Terra High |
|---|---:|---:|---:|---:|---:|
| LIGHT | 4 | 2 | 1 | 1 | 0 |
| STANDARD | 16 | 6 | 3 | 2 | 1 |
| STRICT | 32 | 10 | 3 | 2 | 1 |

## 2. 使用顺序

1. 在仓库外初始化 Task Envelope，并选择 `LIGHT`、`STANDARD` 或 `STRICT`。
2. 在仓库外初始化 DelegationBudget V2 账本。
3. 每次派发前先记录 `INLINE` 或 `DELEGATE` 决策。DELEGATE 必须使用受控原因码，并以不含任务正文的唯一 dispatch key 作为 permit；精确模型请求只允许在宿主适配器校验期间短暂存在。
4. 在 Codex 宿主启动环境中设置 `CP_DELEGATION_BUDGET_PATH` 指向账本，并同时设置 `CP_DELEGATION_BUDGET_REQUIRED=1`。PreToolUse 只有在稳定宿主派发 ID、角色、批准档位与 permit 全部匹配时才允许并原子预占；Required 模式缺少账本路径时会失败关闭。
5. 宿主能够传播 `reservation_id` 时，由 SubagentStart/Stop 自动对账；Codex 0.153.2 未传播时保持 `RESERVED`，不得靠时间顺序猜测。
6. 只有宿主明确证明 Agent 未启动时才能释放预占。Agent 一旦启动，完成、失败或取消都不退款。

示例：

```powershell
python scripts\delegation-budget.py init --ledger C:\safe-state\budget.jsonl --budget-id BUDGET-1 --task-id TASK-1 --project-id PROJECT-1 --repo-fingerprint sha256:<64-hex> --budget-class STANDARD --default-model-profile luna-medium
python scripts\delegation-budget.py decide --ledger C:\safe-state\budget.jsonl --dispatch-key review-data-1 --decision DELEGATE --role reviewer --requested-profile luna-medium --reason-code INDEPENDENT_EVIDENCE_GAIN
```

增强运行时不会自动为每个根任务创建账本。统一预算采用任务级显式激活；未设置上述两个环境变量时，Hook 仍执行自动派发档位上限，但不得把该任务记录为“统一预算门禁已通过”。

## 3. 路由原因

允许：`INDEPENDENT_EVIDENCE_GAIN`、`SEMANTIC_COMPLEXITY`、`EVIDENCE_CONFLICT`、`SECURITY_OR_CONCURRENCY_RISK`、`LOWER_TIER_INCONCLUSIVE`、`MISSING_EVIDENCE`、`INLINE_SUFFICIENT`。

- `MISSING_EVIDENCE` 不能用于模型升级。
- `LOWER_TIER_INCONCLUSIVE` 必须引用上一档结果，并且只允许逐级升级。
- Terra High 只允许高风险安全/并发直达，或有上一档结果的逐级升级。
- 未知角色、非法模型组合、非法原因码或损坏账本失败关闭。

## 4. 批准档位、成本与校准

未显式指定模型时按 Task Envelope 默认批准档位计费，依据写为 `policy-default`。每次派发在启动前一次性预占固定单位；启动后不读取、不推断、不保存宿主实际模型身份或推理强度，也不允许据此补扣、退款或改变结果解释。

Reviewer、Explorer、Worker 使用不同收益指标。子 Agent 自报只能形成 pending 样本；主协调 Agent 带 SHA-256 Evidence 引用最终化后，样本才可进入离线回放。离线校准只比较批准档位的结果价值与单位成本；相邻档位样本不足时结果必须为“不调整”。Proposal 永久保持 `execution_authorization=NONE`。

V7.4.2 及更早版本的 Event V2 与 Budget V1 链保持原始字节级验签能力，但新运行时只读打开并投影允许字段，不会把历史模型身份字段带入 V3 事件、Snapshot、Assessment、Proposal 或发布报告；新记录必须写入独立的 V3/V2 链，禁止与旧链混写。

## 5. Codex 0.154.0 边界

V7.10.0 的 Plugin 窗口是 Codex CLI 0.154.0 与此前十个稳定发行版，精确列表由 `config/codex-compatibility-v1.json` 冻结。本地 Marketplace manifest 必须包含 `interface.displayName`；未来版、预发布版和其他窗口外版本不会自动接纳。0.154.0 修复 Astra 在内置模型选择器中的可见性，在未显式配置模型时将其设为内置默认，并把异步提问说明约束为仅在相关工具可用时适用；这些变化不修改本包已冻结的 Plugin/Hook 合同，也不改变自动子 Agent 仅使用 Luna/Terra 档位的策略。

基础安装必须读回 `installed=true`、`enabled=true`、`version=7.10.0`、十个 Skill 与空 Plugin Hook 清单；增强安装还须核验 `HOST_COMPATIBLE` schema 3 快照、账户 Hook 和受管运行时资产。磁盘已有文件不等于 Plugin 已注册或已启用。

## 任务反馈与优化收益

沿用 V7.5 引入的验证反馈、观察健康门禁、显式启用的增量分析、逐账本场景校准、可检验假设和收益验证关闭；V7.6.2 不再从异步 UserPromptSubmit 注入绑定，身份改由当前仓库外执行信封显式提供。按[受控演进操作手册](evolution/CONTROLLED_EVOLUTION_OPERATIONS.md)执行；项目自动化默认关闭。

## 能力复用与可选门禁

通过[能力索引](CAPABILITY_INDEX.md)完成有界初扫与增量更新，复用前核对候选源码、业务适用性与维护成本。项目门禁默认关闭；V7.10.0 只在显式启用策略下把规范 `apply_patch` 接入 Operation v2：A 创建起点并拒绝，准备后由不同 B 领取许可，匹配的 PostToolUse 回执后才能完成核验。旧 GateTask 永不转换为新许可。参见[验收规程](COMPONENT_REUSE_ACCEPTANCE.md)和[发行验证](releases/v7.10.0/VALIDATION_REPORT.md)。
