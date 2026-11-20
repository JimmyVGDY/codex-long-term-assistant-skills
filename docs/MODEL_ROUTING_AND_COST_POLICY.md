# 模型选择与预算：脚本默认和有界弹性

适用于 Codex Desktop 新默认 `desktop-g6-deterministic-v1`。主 Agent 保持用户当前选择；Reviewer、Worker、Explorer 使用 GPT-6 Luna、Sol、Astra 的 low/medium/high 九档。5.6仅保留显式兼容和历史回放。旧根不得静默换算法、清账或重判结果。

## 执行顺序

1. 使用已安装的 Desktop 派发准备入口，取得脚本计算的事实、默认档位、允许调整范围、共享预算、门禁状态和下一步。
2. 执行 `exact_tool_parameters` 和 `next_action`，显式填写 model 与 reasoning_effort。模型可以理解任务、生成内容、发现风险和提出调整，但不能自行改参数后复用原许可。
3. 需要补读、拆分、调序、升思考档或换型时提交结构化调整建议；由脚本重新核算并返回新决策。缺长篇理由或收益证明本身不阻止默认任务继续。
4. 派发前由控制器原子预占；结果按真实创建、终态、取消和未知状态记账。运行中或终态不明时查询同一调用，不能另开调用冒充重试或免费恢复。

默认定位/提取/机械任务采用 Luna/low，一般任务或信息不足采用 Sol/medium，明确跨域裁决可采用 Astra/medium；最终以脚本结果为准。文件数、行数、路径命中与一次失败是信号，不是难度或漏洞证明。自动xhigh/max/ultra禁止。

## 证据不足与门禁

所有本项目活动门禁保持开启。缺理由、质量卡、收益卡、历史样本、非关键材料或可选检查结果时，脚本返回默认、降级或其他可执行下一步，不通过临时关闭门禁继续。下游Hook不得再次把相同缺证据变成资格拦截。

能力资料未知不等于所有型号不可用：优先读取宿主提供的能力信息；仅证明不足时采用带未知标记的有界默认尝试。真实接口不可用、所有型号明确不可用或预算耗尽时，报告实际限制并继续可行的本地工作，不能假称已派发。

已确认的越权、安全违规、项目身份冲突、账本损坏、超预算或制品哈希不符，只限制对应动作。用户未授予的权限不能由默认档替代；外部平台权限和信任控制不由此规则关闭。

允许继续与验证通过分开记录；缺系统隔离证明只能称logical-readonly，缺结果不能补造PASS。若用户明确要求系统隔离且宿主无法提供，只限制该受限动作。

## 预算与弹性

- 脚本计算授权额度、已扣记、在途预占和后续必需预留；相同调用不重复扣记，拆分不重置根预算。
- 规划单位是版本化配额，不是实际credits或质量评分。未知实测费用保持UNKNOWN。
- 调整范围、次数、并发、深度、重试和退避均读取运行时策略；必要降档不挤占升档次数。只有更贵的6系列可用但现有额度允许时，脚本可选择最便宜可用档并记录能力回退。
- 模型提出的风险和任务类型先标为语义建议，不直接晋升为已验证事实或用户授权。
- 只预留确实必需且满足工作约束的后续步骤；证据不足不自动追加统计研究，也不因一次失败强制升high。
- 相同材料没有新信息不重复评审；可恢复故障按类别与剩余预算、总时间处理，不无限重试。

## 可计算标准与自然观察

范围指标记录定义、单位、来源、计算版本和缺失语义；文件数和路径命中只作规模与范围信号。权限约束、规划预算、任务适配、证据状态分别处理，不汇成一个总分。事实采集按整次时限返回已取得材料，未知保留 UNKNOWN。

必需步骤执行时把自己的预留转为在途，不重复扣除；只能选择该步骤允许的能力档位。宿主证明未创建的尝试允许重新准备，但原尝试计数保留。根中明确登记的拆分通过 origin_work_item_id 共用升档计数；没有可信谱系的工作共享根内调整额度，改名不能清零，默认派发仍可继续。

Stop 从既有账本生成单根观察：按批准档位和角色统计尝试、已扣与在途规划单位、原生终态以及预占到终态入账耗时。重试不充当独立任务；原生 PASS 不充当业务质量证明。缺最终质量裁决和实际费用来源时对应指标保持 UNKNOWN；观察不触发额外模型调用或自动改策略，采集故障不阻塞已授权工作。

## 兼容与回放

先读取根任务绑定的策略版本。旧V3/V4账本继续按[历史模型路由](../skills/multi-agent-independent-review/references/reviewer-model-routing.md)及各自冻结合同解释；新默认不要求取得其统计资格，也不把缺少旧资格卡视为违规。同一聊天换策略通过可验证交接保留旧账目、未结项和迟到事件归属。

## 按项目试用版本化目录

`desktop-catalog-v2` 只在明确选择试点的项目中用于新根。未选择的项目沿用既有策略。管理员通过当前包的统一管理入口预览和应用默认选择。审查包可传 --delegation-ledger 来绑定已存在的根。已派发调用的型号、强度、费用归属和迟到回执继续使用原根摘要。

```text
cp-assistant routing-policy show --repo-path <repo>
cp-assistant routing-policy preview --repo-path <repo> --policy-id desktop-catalog-v2 --revision <n>
cp-assistant routing-policy apply --repo-path <repo> --policy-id desktop-catalog-v2 --revision <n> --confirm <request_ref>
cp-assistant routing-policy refresh-capabilities --repo-path <repo> --session-id <native-session>
cp-assistant routing-policy rollback-check --repo-path <repo> --target-manifest <bundle/manifest.json>
```

切回时预览并应用 `desktop-g6-deterministic-v1`。新默认只作用于以后创建的根。替换读取器前检查未结调用、仍活动的任务、策略摘要及账本格式。机器清单和当前读取器支持 /1、/2、/3。

目录逐型号登记精确宿主名称、强度、规划单位、并发组、角色偏好与优先级。规划单位仍按原有的 1、2、4 权重组合。排序先筛授权、容量、并发、必需步骤和可用组合，再按任务适配、规划单位、可比耗时与显式优先级选取。新增条目可以先处于 shadow 或只在试点使用。改费用或精确映射时创建新快照并保留旧文件，将新摘要加入读取器索引。每个根按其摘要重放。

支持 native 的直接分类行 `task_kind=mechanical`、`task_kind=lookup`、`task_kind=cross_domain_adjudication` 等。单独的“定位符号 名称”按直接定位处理。指定型号可写 `model=gpt-6.2-sol reasoning_effort=medium`。未知明确选型会返回具体原因。在已选择试点的项目中，可另加独立一行“试用所选精确档位一次”，明确受原生回合、项目和根预算约束的一次试选。该组合必须出现在当前可用来源中，并尊重宿主的明确排除。一次许可不代表支持已验证。实际创建回执与账户目录分别提供证据。

同项目使用 `routing-policy compare --repo-path <repo> --policy-id desktop-catalog-v2` 离线对照，可用 --ledger 限定实际根。需要纳入质量判定时，通过 --project-profile 和重复的 --evidence 提供项目证据台账中已登记的父协调者 validation 记录，subject 为 routing-quality/1，source 为 parent-coordinator。引用绑定 permit、terminal、policy、root、repository、initial_baseline 及对应角色的指标。复审记录 findings、accepted、false_positive，执行记录 accepted、rework，定位记录 hit。--save-timing 仅保存同策略、同角色和任务类别下有足够独立根的耗时，用于同价打平。实际 credits 缺计量时保持未知，学习报告不会自动改权重。
