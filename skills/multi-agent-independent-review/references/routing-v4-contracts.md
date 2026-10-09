# GPT-6 路由 V4 的数据与事务契约

本设计面向 Codex 桌面端。内部构建、校验和安装脚本不是独立 CLI 产品支持。
V4 把定位与质量资格、升档/换型号收益和资源审批分开处理。
旧 four-tier-v1、reviewer-matrix-v2/v3 及其账本继续使用冻结解释器。

## 1. 信任边界

所有 JSON 使用有界读取、重复键拒绝、闭合字段、严格类型和规范摘要。
摘要只能证明内容一致，不证明发行者身份，也不单独授予发布资格。
来源、发布批准和可用性分别核验。

三类卡均由以下对象绑定：

- CardBundle：schema、bundle_id、project_id、repo_fingerprint、policy_id/digest、scenario、origin、created_at/expires_at、experiment_ref、cards。
- Experiment：schema、experiment_id、相同项目身份、origin、评判规则摘要、预登记比较与 alpha 配额、独立样本、桌面任务/调用/回执引用。
- CardPublication：bundle_ref、experiment_ref、approval_ref、批准记录摘要、项目/任务/仓库/基线、有效期、状态和修订号。
- RootBinding：Project Profile、任务信封、policy、已发布 bundle/成本基准、桌面能力快照的引用。

Publication 的 issuer_task_id、issuer_baseline 标识实验发行时的任务与基线；
consumer_root_binding 单独保存消费任务及其当前代码基线，两者不得混用。
publication 的 consumption_scope 明确为 issuer-only 或 project-bound-reuse。
后者允许相同 project_id/repo_fingerprint、policy/算法、提示/工具/评判契约
和已批准场景范围内的新任务复用；业务代码基线可以不同，但新的审查结果、
permit 与 Evidence 必须绑定消费任务当前基线。

make-effective 批准在发行时校验并消费，绑定 bundle 摘要与 consumption_scope 摘要。
已批准的 project-bound-reuse 不在每个新任务重复消费同一批准；
消费根初始化时固定 Publication 引用和当前 revision，再在每次预占前检查
未撤销、未过期、场景/运行契约仍匹配。超出项目或场景、契约变化或撤销后重启用，
必须重新实验/核验并发行新 Publication 与新批准，不能沿用旧授权。

origin 仅允许 synthetic、desktop-evaluation。synthetic 只服务测试；
desktop-evaluation 在独立实验状态完成，须有可核验的桌面调用关联、主协调者最终化及发布批准，才能进入生产资格。
EVALUATION 状态本身不授予生产资格。

QualificationCard 绑定样本结果和绝对验收条件；GainCard 绑定同一批配对结果、
完整统计参数、区间算法、种子和产物摘要；CostCard 绑定计量口径与冻结采样摘要。
加载时重算关键摘要和确定性统计，不接受调用方提交 qualified=true 作为依据。

发布入口复用 Project Binding 与 Approval(make-effective)：
批准必须属于当前项目、任务、环境和基线，并绑定待发布 bundle 的摘要。
受控发布操作在锁内消费批准并追加 Publication；根任务只接受已登记且未撤销的精确引用。
修改卡片、替换实验、过期或撤销 Publication 均使新的派发失效。

上述机制属于已有工作流级信任边界。同一系统账户能够任意篡改全部本地状态时，
不能把完整性字段称为操作系统隔离或第三方数字签名。
没有完整宿主关联时保留未验证，不收集后台实际运行型号。

## 2. 18 个组合与资格范围

目录明确声明 GPT-5.6 Luna/Terra/Sol 和 GPT-6 Luna/Sol/Astra 的 Low/Medium/High。
完整 profile ID 包含代际；旧 luna-low 等 ID 的历史含义不改变。
默认 Reviewer 候选是通过场景验收的 GPT-6 子集。
5.6 Luna High、Terra Low 在旧策略中未登记，仅进入实验目录，不补写旧快照。

场景键包含 role、phase_key、S/D/R、tags、context_bucket、tools_profile、
speed_mode 和提示模板摘要。phase_key=repair 仅由 post+repair 归一化得到。
不同场景不得仅按同名型号借用资格；跨项目样本不混入同一校准队列。

## 3. PhasePlan/1

PhasePlan 保存 schema_version、plan_id、revision、identity、slots。
policy/bundle 来源固定在根账本 sources，完整分配 witness 随初始化、修订和选择事件保存。
每个 slot 包含：

- slot_id：根任务内唯一，数量受总派发上限约束。
- scenario：role、归一化 phase、语义/推理/风险级别、标签、上下文、工具、速度及提示摘要。
- independence_required：是否必须独立判断；风险等级 2/3 不得关闭。
- depends_on、condition：always 或 repair-after-post。
- options：profile、qualification_ref、cost_ref、完整资源向量。
- status：PENDING、RESERVED、AWAITING_RESULT、SATISFIED 或 WAIVED。
- active_reservation_ref、accepted_result_ref、release_evidence_ref。

资源向量为 units、attempts、astra_attempts、astra_high_attempts。
可行见证必须为每个待履行槽位选定真实选项；不能拼接各维独立最小值。
有界搜索耗尽时返回 PHASE_PLAN_SEARCH_LIMIT，不能把未知写成无解。

持久化转换：

| 事件 | 前置状态 | 原子效果 |
|---|---|---|
| PLAN_INITIALIZED | 无计划 | 固定槽位、候选引用及可行见证 |
| PLAN_REVISED | 无身份变化、无质量条件降低 | 增加 revision；保留已消费资源，重算未完成分配 |
| DISPATCH_RESERVED | PENDING、有效 witness 与当前 revision | 槽位转 RESERVED，消费 permit，写入预占 |
| HOST_CREATED/STARTED/STOPPED | 匹配调用与 Agent 引用 | 更新宿主状态；STOPPED 不直接证明业务通过 |
| RESULT_ACCEPTED | AWAITING_RESULT、结果及当前范围核验通过 | 槽位转 SATISFIED；保存结果引用 |
| REPAIR_REQUIRED | post 结果存在阻塞 | 保留 repair 槽位与预算，不能释放为其他任务额度 |
| SLOT_WAIVED | 当前 post 合并已通过且无未解决修复 | 仅释放对应条件性 repair 槽位；保存合并证据 |
| NOT_STARTED_RELEASED | 存在可信未启动回执 | 退还单位但不恢复尝试次数；槽位可在新尝试下继续 |

可信 HOST_STOPPED 一旦能与本根 HOST_CREATED 的 Agent 引用唯一关联，
在同一条追加事件的投影中把 reservation 标为 COMPLETED，并将槽位
RESERVED → AWAITING_RESULT。这里仅表示调用已经结束，不表示复审通过。
若 stop 先于 created 到达，先保存未关联观察；后续 created 追加时在同锁投影
完成上述两项转换。相同回执幂等，冲突终态拒绝，晚到 start 不回退已完成状态。

任务树回执必须精确匹配本次预登记的 /root/任务名。回调使用内部 ID 时，仅从宿主
agent_transcript_path 指定、且位于当前 CODEX_HOME/sessions 内的文件读取第一行身份头，
上限 128 KiB；核对父会话、子任务 ID、仓库、角色、深度和任务名后追加身份关联。
不扫描正文、不读取实际模型字段、不按时间先后猜对应关系。身份头格式属于经验证的
桌面适配，不能当作稳定公共接口；路径或格式不满足条件时保持未关联，不能完成或退款。

可信创建失败且明确证明未启动时，NOT_STARTED_RELEASED 在同锁投影中将槽位
RESERVED → PENDING，清除 active_reservation_ref，保留已消费的 permit 和尝试编号。
缺失创建回执、未知失败或取消请求不触发该转换。崩溃恢复只重放已有完整事件，
不从文件存在或通用 status 推导 HOST_STOPPED 或“未启动”。

RESULT_ACCEPTED 的“核验通过”指结果身份、范围和内容契约有效。
宿主已明确 CANCELLED/FAILED/PARTIAL/BLOCKED 时仅接受 incomplete，不允许结果覆盖该终态。
宿主 UNKNOWN 不提供复审结论；必须另行核验结果身份、当前基线、完整检查范围和内容，
且接受结果后仍保留宿主 UNKNOWN，不能反写为宿主 PASS。
post 的 blocking 完成初次审查并使预留 repair 可执行；修复结果以 supersedes 关联原阻塞，
不能据初次槽位 SATISFIED 把整个任务标为通过。pre 或 repair 的 blocking，以及任何
incomplete，都使当前槽位保留为 PENDING。再次派发必须引用最近结果，并有真实的新证据、
基线或审查包；所有消费记录与次数保留，不自动释放必需保留量。

mandatory 槽位不能因额度不足删除。调整 S/D/R 或标签不得降低未履行边界；
确需改变业务范围时须有独立的范围变更依据，而非重新开账本。
在途 reservation 的输入不可被 PLAN_REVISED 修改。

当前审批检验所有其他未完成槽位仍有可行分配，保护 post 与 repair。
根、角色、阶段、次数、并发和深度限制分别校验，不能互相兑换。

Astra 在途并发上限固定为 1，与根 max_parallel 和累计 astra_attempts 分开约束。
状态读回提供 astra_active 与 astra_parallel_available；RESERVED/STARTED 计入在途，
可信终态关联或可信未启动释放后才退出在途计数。完成不退还累计单位或尝试次数；
未启动只按既定证明退还单位。原子预占再次校验该上限，不能靠伪造选择快照绕过。
普通组合仍可在根并发上限内并行。

## 4. SelectionDecision/2 与一次许可

SelectionDecision 的摘要绑定标准化任务条件、policy、卡片/Publication 修订、
PhasePlan 修订、桌面能力快照、代码基线、经济锚点、赢家和动态预占量。
本对象还没有派发权限。

Root 主协调者生成 permit_id 和 256 位 nonce。仅 nonce 摘要写入账本；
实际 nonce 仅随本次控制器响应返回。普通日志、计划与审查结果不得保存 nonce。
permit 绑定 decision_ref、slot_id、attempt_no、登记角色和完整请求 tuple。

reservation_id 从 budget_id 与 host_dispatch_id 确定性生成。
主账本维护 host_dispatch_ref 和 permit_ref 的唯一映射。
同一锁内重新读取所有相关修订，重算选择，确认赢家不变，然后以单条
DISPATCH_RESERVED 事件同时完成 decision/permit 消费及 reservation 创建。
没有“已消费但无预占”的半状态。

| 重复或碰撞 | 结果 |
|---|---|
| 同 host call、同 permit/decision/tuple，仍为 RESERVED 且无创建回执 | 返回同一 reservation，标记幂等，不重复扣费 |
| 同 permit，不同 host call | PERMIT_ALREADY_CONSUMED |
| 同 host call，不同 permit/decision/tuple | HOST_DISPATCH_COLLISION |
| 已有创建回执、STARTED/COMPLETED 后再次派发 | ATTEMPT_ALREADY_STARTED |
| 已可信释放的 reservation 再次派发 | RELEASED_ATTEMPT_REUSE |
| 旧 ledger/plan/card/capability/baseline 修订 | STALE_SNAPSHOT；不派发、不改选赢家 |
| 迟到的相同回执 | 幂等归并；不增加扣费或退款 |
| 未知取消、超时、缺回执 | 保留未完成与已占资源，不能证明未启动 |

宿主执行是否幂等与本地预占幂等分别验证，不以文件锁证明宿主只执行一次。
崩溃后以完整账本事件为权威恢复 Review State 投影，不猜造模型结果。

## 5. 选择与统计

先形成角色允许、桌面可请求、定位覆盖、质量合格、成本同口径且资源可承受的集合。
按 C_U、T_U、profile ID 选择经济锚点。

可选质量升级须有直接 GainCard，质量改善下界至少 3 个百分点。
economy 保留锚点；balanced 限制计划消耗不超过锚点两倍、延迟不超过 1.20 倍；
deep 在根边界内允许更高的已证实质量投资。
R=3 使用 deep 行为但不增加根额度，也不指定某个品牌或 High。
增益下界距最佳不超过 1 个百分点时，优先较低消耗。

质量与误报使用预登记配对不一致事件的精确二项区间，并分配整体 alpha 预算。
重复运行按案例聚合；同一桌面任务中的相关样本还须按任务簇处理，
不能用重复回执或拆分案例伪造独立样本数。
统计基础库另提供配对重采样算法；结果必须明确是否实际执行该项计算。
当前线上选择比较已批准成本卡的计划值，不把代理单位或经验区间冒充真实账单硬上限。

## 6. 兼容与验收

新增 policy V4、选择卡 V2、Budget V4、Review State V9、Result V6、Sample V4。
旧格式及成本算法不原地改变。恢复时先读取任务固定版本，
不能先用当前默认模型表拒绝旧请求。

必须验证卡片篡改/跨项目/失效/撤销、来源标记与宿主关联、持久化 hold、
并发重复预占、崩溃恢复、乱序回执、未知取消、旧账本重放及桌面端真实请求。
合成测试不提供模型质量资格；源码、包、安装、加载、派发与公开发行分别读回。

## 7. 桌面管理与读回

内部入口为 `scripts/routing-v4.py`。状态和评测产物默认保存在仓库外。

| 命令组 | 作用 |
|---|---|
| init / bind-desktop / status / retire-desktop | 建根预算、按根会话与仓库登记、读回及保留关闭墓碑 |
| review-init / prepare / result-template / result / review-status / review-close | 固定审查归属、计算组合、记录并验证 V6 结果、保存 V9 结论 |
| eval-plan / eval-suite / eval-request / eval-result / eval-advance / eval-assemble | 预登记场景与配对实验、合并固定实验集、生成精确请求、记录判定并保留累计消耗 |
| bundle-build / publish / revoke-publication | 计算资格与收益、消费精确批准、撤销生产使用资格 |
| sample-pending / sample-finalize / sample-report | 建立待审观察、绑定最终化证据、重新读回来源后分组 |
| revoke-prepare / close | 撤销未消费许可、关闭根账本 |

评测清单保存 prompt/gold/rubric 的摘要与固定比较族；工具正文只包含审查材料，
不包含标准答案。登记后不能更换案例、遗漏失败试验或重复使用同一调用回执。
主协调者判定保存结构化布尔字段与产物引用，原始正文不写入 Hook 或账本。
试验结果的 pass 表示完整采集，模型是否答对由独立 grade.passed 表示。
所有试验完成仍不等于任何模型取得生产资格。

eval-suite 将最多 10 个已登记场景清单固定在同一根账本来源中，冻结实际试验总数。
每组只执行其预先声明的比较，不把各组模型与全部案例做笛卡尔积；案例身份不能重复，
同场景同组合成本不能冲突，所有组共享同一成本单位、累计消耗和根上限。
各组的标准答案、规则及原生回执分别绑定原协议，不能跨组拼接资格样本。

成本卡的 declared_proxy 表示已批准计划代理量。当前没有可归属的桌面单次计费回执，
生产加载拒绝 measured_codex_credits。资源报告不自动改变成本卡。
原生观察时长包含预占、调度与停止回调开销。

Sample V4 报告必须重新读取根账本、不可变 V6 结果和最终化 Evidence；
同记录重复输入去重，冲突记录拒绝。最终化时核验当前代码基线；历史报告核验
固定来源及当时基线，不把旧观察当作当前代码验收。

桌面根登记与显式环境绑定冲突时拒绝。损坏登记不得静默退回策略模式，
另一项目或另一根会话不扫描、不复用该登记。关闭墓碑持续选择原已关闭账本，
避免清空预算后继续派发。登记属于逻辑工作流控制，不是系统只读证明。

V4 根绑定生效期间，followup_task、send_message、send_input 与 resume_agent 不开展新审查，也不向试验注入额外材料；这些调用在派发前拒绝。新轮次必须使用新的独立调用和许可。暂停/取消不据此退款。

`add-evidence` 只追加同项目、同任务、当前基线和已有场景的 Evidence；不覆盖旧引用、不修改策略或已花费资源。追加事件推进选择修订，使旧准备许可失效；未消费许可须先撤销再重算。基线已过期的结果仅可保存为 incomplete，不能据此关闭为 PASS。

## 8. 审查读取协议第二版（本地候选）

`desktop-authoritative-context/2` 必须在新的评测根初始化时显式选择；默认仍是 `/1`。
Budget 5 的不可变 `context_runtime.transport_mode` 固定本根的解释器，旧根不原地升级。
这不建立独立 CLI 支持，也不改变冻结 V3 默认或生产工具覆盖门禁。

- 控制器用同一个生成器构造固定读取命令、结构化参数和完整 `functions.exec` 程序。
  普通 Windows 路径使用正斜杠，特殊命名空间通过 JSON 序列化保留；模型不自行转义。
- 每个子任务最多三个读取尝试，总窗口五秒，从首次尝试起算。只有创建回执尚未到达、
  成功输出是预期字节的严格前缀时可恢复。未知输出、非零退出、权限、身份、基线、
  材料摘要和命令不一致均终止。同一宿主事件幂等；新模型派发仍正常扣减。
  窗口同时约束重试准入与完成验收；超时后到达的材料保留为交付事实，但恢复不能通过。
  这不承诺强制中断操作系统 I/O。
- 原始尝试、失败原因、恢复读取及材料交付均保留。不会把旧 `/1` 试验中禁止重试的
  失败重新判为通过，也不因读取恢复重复扣减模型派发额度。
- 模型只提交五个语义字段；Finding 的采纳、修复和回归治理初值由控制器补齐。
  取消抄写长回执的前提，是 `SubagentStop` 的可信子任务路径、关联会话头、材料交付
  和该子任务唯一最终回答全部匹配。账本只记录最终回答及语义正文摘要。
  首次关联固定日志规范路径及稳定文件身份；最终头部和正文来自同一个打开的句柄。
  复制相同头部的另一份日志或替换原文件不能接管证明；正常追加仍可接受。
  缺失或冲突保持不完整，不能由主协调者补造证明；取消不能被最终回答覆盖。
  内部 `failure-accounting` 只为已停止且有可核对失败条件的调用生成显式控制器收口记录。
  它只能是 `incomplete`，不能改写原回答或替代已验证成功；原生回答是否验证单独记录。
- 新跟踪格式 `desktop-evaluation-trace/3` 含最终回答与恢复记录引用；旧资格卡消费者
  不接受它。原生验收和生产资格是独立门禁，不由合成测试自动授予。
- 分别报告材料送达、协议合格、已评分样本上的语义正确率、评分覆盖率与完整流程通过率。
  读取失败不从完整流程分母消失。排除样本和失败尝试的资源消耗仍计入全部实际调用；
  未知费用保持未知，不把代理估算当成账单。

新版六例材料使用独立案例 ID、来源摘要、明确输入域和可执行预期判定。
旧材料、旧 gold 和原评测结论保持历史原貌。本地验证不批准模型默认迁移。

## 9. 读取协议第二版的资格证据（开发中）

显式 `routing-experiment/2` 消费 `desktop-evaluation-trace/3` 或 `/4`，同一实验不混版本。
旧实验 `/1` 继续拒绝新跟踪格式。新消费者核验原生回答、恢复、材料交付和已接受结果。
`/4` 将原生原文证明与结构化语义证明分开：模型自己的不完整或格式错误回答可以计为
失败样本，不能计为通过；没有原生原文、材料或工具证明的控制器收口仍不能充当模型样本。

`routing-trial-result/2` 将主协调者评分绑定到原账本的结果引用、原始回答摘要、
案例、金标准、评分规则、请求组合和重复编号，首次保存后不覆盖。
原生审查结果和费用仍由原账本拥有；评分不会改写模型结论或补造原生回执。
从磁盘实际字节计算金标准和评分规则摘要，不能使用尚未落盘的字符串摘要。
相同回答正文可以来自不同真实调用；正文可按摘要共享，归属信封按派发分别保存。

内部 `qualification-size-plan` 按现有精确区间计算零分歧条件下的参考样本量。
一次比较需要252个独立干净案例、99个独立质量案例；干净案例属于质量案例，
不能重复相加。它是规划参考，不替代真实区间、90%质量底线、关键失败和独立性门槛。
模型存在收益或损失时仍以原算法重算；不得为通过而缩小比较族或拆分重复问题。

内部 `qualification-grade`、`qualification-assemble` 只形成未发布的证据。
新卡片绑定 `qualification_source`：总计划和全部试验来源文件的路径/摘要，以及可重算
审计引用。发布和消费都重读全部登记账本及评分来源；缺段、在途、未评分、引用变化或
重复调用不能通过，不能只传成功子集。既有生产拒绝、V3默认、5.6兼容和自动派发显式
model/effort 的约束保持不变；完整证据仍不自动激活默认。

`qualification-study/1` 在任何派发前固定所有 case/profile/repetition 单元、独立簇审阅
Evidence、分段和总资源。每段最多64次尝试，各段资源之和不能超过总额度。同题/同根因
或完全相同 Prompt 不得伪装成多个独立簇。原生根的费用卡绑定整个 study 摘要；改变计划
或另开未登记账本不能补充额度。缺段时资源合计明确不完整，真实计费继续 UNKNOWN。

工具证明同时核对原始日志位置/文件身份、最终回答、唯一控制器程序及实际模型可见输出。
仅允许程序外层 ASCII 空白差异；新增调用、托管搜索、其他工具和外层输出截断均拒绝。
本地 Hook 约束和事后使用核验仍是逻辑只读，不是系统隔离，也不能撤销工具副作用。
官方覆盖限制见[Hook工具覆盖](https://learn.chatgpt.com/docs/hooks)。

## 10. 本地默认激活（未取得资格时不生效）

`desktop-default-activation/2` 新默认固定完整资格计划；`/1` 仅保留历史读取与显式恢复。
`default-qualification-plan/1` 从冻结策略生成七正式角色 × pre/post/repair 的21单元，
绑定18精确组合的完整原生开发筛选、事前审阅的冻结选择、包digest和正式协议引用。
正式确认只比较每单元事前选定的一个GPT-6组合与5.6对照，保持原统计门槛；
18组合不全部重复正式统计。开发与确认的来源问题、根因、簇或prompt重叠拒绝作为holdout。
缺任一角色、阶段、筛选组合、完整分母或冻结正式协议均不能切默认。普通Worker/Explorer
不进入Reviewer评测资格。项目最多登记100份来源，单任务仍只消费最多10份固定成员。

激活仍按 PREPARED → INSTALLED_VERIFIED → ACTIVE 推进。消费批准前持久化同次操作意图，
绑定源、任务、基线、批准指纹和原指针；ACTIVE或批准已写而指针未发布可用同次批准
幂等恢复，不重复消费、不覆盖另一当前指针。独立批准的显式旧策略回滚可恢复缺失指针，
回滚自身的指针写失败也可重试。过期、撤销、内容变化和资格不足仍失败关闭。

当前Desktop的task_complete可省略尾随记忆引用元数据；仅接受与回显完全相同的正文及
严格单个已知元数据容器。最终取证仍返回和哈希全部原始文本，不删除或改写元数据。
带尾随元数据的回答仍不是协议JSON，不因此获得模型通过或统计资格。

## 11. 显式64KB材料档

新根可显式指定 `context_profile=bounded-review-64k/1`，仍使用读取协议 `/2` 的有限恢复
与原生结果绑定。该档固定序列化bundle上限64000bytes、reader输出上限65536bytes，
每个bundle最多64个材料快照。每次文件读取和总序列化结果都检查边界，拒绝链接、路径
越界、摘要变化和超限，不截断后继续审查。旧根未登记该档时保持8000bytes。

新档使用bundle/2，必须匹配根runtime档位；场景固定 `context_bucket=bounded-review-64k`
与 `tools_profile=desktop-context-reader-64k-v1`。旧8KB资格不能直接升级到该档。
控制器同时生成内层读取和外层code-mode的输出预算；实际模型可见输出仍须与交付摘要
逐字节一致。上限放大是工具合同变化，不能由本地代码测试自动授予模型场景资格。

Desktop 的 PostToolUse 可能提供截断的显示预览。64KB档仅在原始子任务日志中找到同一
工具调用、同一轮次、同一工作目录和固定命令，且成功退出、原始stdout与聚合输出均与
批准材料逐字节相等时，才可核验内层输出；预览还必须与该原生事件的格式化输出一致。
缺失、重复、文件替换、命令或时间不符仍拒绝。外层code-mode的完整程序及模型可见字节
继续独立核验，内层输出证明不能替代它。首行`// @exec`输出预算指令须完整保留。

## 12. 普通委派与复审共用预算

新默认的读取协议 `/2` 同时固定 `ordinary_contract=frozen-v3-four-tier/1`。未登记该标记
的旧根保留原义。Worker/Explorer 仍仅用 GPT-5.6 Luna Low/Medium、Terra Medium/High，
冻结权重为1/2/4/8；必须显式选一个档位，不从父模型继承，也不借用 Reviewer 资格卡。
固定策略授权使用 `selection_basis` 区分于统计资格；不会生成经验质量或收益证明。

普通委派先核验当前任务范围 Evidence、批准正文、模型能力和共享额度。后续预审、复审
及返修槽位继续参加总资源与角色/阶段可行性计算。普通任务不支持承诺墙钟截止时间。
实际派发正文必须与批准正文相等；独立 fork、父子原生身份、唯一 permit 和创建回执仍
是门禁。创建回执到达前工具保持隔离；核验后普通任务可按其原任务范围和宿主权限使用
正常工具，不能把 Reviewer 的固定读取器及逻辑只读限制套给 Worker/Explorer。

普通结果使用独立的原生文本证明与 `ORDINARY_RESULT_ACCEPTED`，无需复审 JSON。
原生完成不自动满足任务：父级须提供当前仓库/项目/任务的 validation Evidence，来源
为 `parent-ordinary-task-validation`，并绑定 `ordinary-reservation:<reservation引用>`
与 `ordinary-verdict:pass|incomplete`。明确失败、取消、部分完成或阻塞的宿主终态不能
验收为 pass。incomplete 保留费用和历史；新增证据后重试须引用上一结果，精确覆盖未
解决的旧结果。相同事件重放不重复扣费。普通结果不会进入 Reviewer 状态、资格评分或
资格跟踪；新默认的准备还必须校验包内具备此普通委派合同。

内部 `ordinary-prepare` 与 `ordinary-result` 管理该过程，仍不是独立 CLI 产品适配。
生产根继续须具备完整 Reviewer 统计资格、有效项目激活和已安装内容读回。普通兼容测试
不能授予新模型资格，也不能越过默认迁移门槛。

## 13. 独立阶段评测

正式阶段样本可在读取协议 `/2` 的新评测根显式登记
`evaluation_contract=isolated-review-phases/1`。该合同仅适用于 EVALUATION：全部槽位
必须为登记 Reviewer、condition=always、无工作流依赖。普通角色、生产根、旧读取协议
和带有真实返修依赖的槽位均不能使用。未登记的旧根仍须有真实阻塞 post 结果，才可
首次派发 repair；生产返修门禁保持原义。

该评测核验模型如何审查冻结的 pre/post/repair 材料。repair 样本须在批准正文中提供
原问题、前次报告、修复候选和对应验证材料；来源与 gold 审核不能被阶段标记替代。
独立样本不创建生产阻塞结果、不覆盖真实前次复审，也不证明真实任务的阶段流转。
请求/回执/材料/原生最终回答/全部评分分母与费用仍走同一原生证据链，不能以 controller
收口或合成日志代替模型来源。新合同不改变统计门槛、不扩大分段或总资源；默认激活
仍须完整统计资格及生产流程验收。内部 init 提供显式 --evaluation-contract 参数。

## 14. 综合结果与案例适用性接口（未接入派发）

`review-vector/1` 固定七个维度，模型只提供各维度的状态、Finding、检查范围、未验证项
和摘要。控制器提供完整适用性scope：applicable、not-applicable、unknown；已确定
的适用/不适用必须有Evidence引用。接口只检查结构，引用格式不证明实际Evidence已核验。
模型不能把应检查或缺证据的维度改为not-applicable；未知维度须incomplete，有未验证
依赖的维度不能完成。没有实际适用维度时总结果仍incomplete，不自动通过。

`validated-review-vector/1`由控制器汇总，保留已确认的阻塞Finding，缺证据优先表现为
incomplete。固定治理字段继续由原语义扩展器补齐；七维共享最多64个Finding、总回答
最多1MiB。跨维度ID冲突、缺维度、未知维度和模型注入费用/回执字段均拒绝。

`review-dimension-view/1`是同一结果的展示/评分视图，带同一vector_ref、原模型payload
引用和scope引用；它不是独立模型调用、原生receipt、旧Result或已认证样本。旧消费者
继续拒绝向量外层，不能将一个调用展开成七次预算扣费或七个独立问题。

案例矩阵按phase×dimension×cluster聚合真实适用的clean/defect/critical标签；未知或
不适用不填分母，同问题或根因跨cluster别名拒绝，变体clean标签冲突须先冻结选择。
输出只报告覆盖缺口，不验证正式准入，也不授予统计资格。

显式 `review_contract=integrated-review-development/1` 仅允许 transport/2 的 EVALUATION
根，并与普通委派合同互斥。注册 Reviewer 仅作开发调用身份，不代表已发布综合角色。
`integrated-review-input/1` 将 phase、instructions、scope 和带摘要的 materials 全部放入
自包含 business_prompt；预登记摘要覆盖所有实际输入。scope 的引用必须对应实际交付的
材料字节，仍不等于材料已获得独立金标准审核。模型须返回七维向量；Hook 绑定原生回答，
控制器生成 Result 8，携带开发合同与完整输入引用（覆盖 scope），按总状态完成一次结果
接收和预算记账；材料后来不可用时，取消/失败仍能按冻结输入身份收口。
原始向量按内容摘要保留。未知维度导致 incomplete，已确认阻塞保留；取消与控制器失败
收口不能成为通过。旧 Result 7、普通委派和原预算上限保持原义。

本入口可运行三个阶段的开发桥接，不授予正式资格。旧 trace 和评分消费者明确拒绝此
合同，生产根初始化也拒绝；综合角色、正式比较/资格消费者及容量扩展仍待实现与验收。
不得把开发集结果复制成七个旧 Reviewer 样本，也不得据此安装或切换生产默认。


## 12. 有限研究承接 seed（尚未原生验收）

`bootstrap-code-review/1` 仅用于已经明确授权的代码复核，使用独立的
`bootstrap-review-plan/1`、材料 manifest 和阶段 grant；没有统计 gold、clean 或
critical 标签。传输继续复用 EVALUATION 预算机制，统计评分与 trace 导出明确拒绝此类型。
新研究入口不修改旧 V4/V5 根、intent、封存结果或费用，也不发行资格或切换生产默认。

阶段 approval 只消费一次；最多两个固定段、每段最多四次调用，唯一 claim 永久划拨预分配
额度。摘要依赖为 plan → manifest → grant → admission → claim/transition → head，
不回填祖先。`request_ref` 明确定义为严格 V5 request 将控制器动态 `expected` 置空后的
完整内容摘要，其余业务字段均固定；动态快照仍由预算选择器核验。成本来源绑定独立材料
引用，不能引用包含成本自身的 plan 摘要。过期/撤销后只恢复已耗额元数据，新的派发继续拒绝。

锁顺序为 session → stage → ExpectedSpawn → budget。允许 spawn 之前保存唯一真实
task_path/role/depth、host call 和 reservation 索引；Start 从原始可信头部定位，不依赖
POST 先到或父 call-ID 出现在 Start。POST 使用固定 call 索引，旧子事件仍归原段。
索引持久化失败保留预算事实并阻断重复 spawn，不推测退款或创建回执。

这只是有限 bootstrap，完整 study/2、整轮 campaign 与正式统计消费尚未接通。
通过合成事务/事件验证不代表 Desktop 原生验收或系统只读；原生代码复核前不进入正式研究。


## 13. 显式同call通知交付

`delivery_contract=same-call-notify/1` 仅与MODE_V2及64KB档组合；当前不与ordinary_contract或review_contract共用。原single-output程序/proof保持原解释。
一次现有reader取得完整raw，再由同一固定Code Mode程序投递最多8片，每条完整UTF8通知载荷<28000bytes，全部原材料和64000bytes业务界不变。普通完成可能先到，notify非Promise；不以await/sleep推测完成。每条顶层metadata预算、同call、顺序/count/offset/hash、独立complete、小摘要和final先后均核验，缺失或不足拒绝。
原reader事实与累计CONTEXT_NOTIFY_ATTESTED分开封存；最终模型回传complete收据，收据不是阅读证明。正式评分重新核验desktop-tool-surface/2全集且绑定同一raw/final，不能仅靠旧raw receipt。


## 显式受信wire通知与派发意图元数据恢复

`same-call-notify/2`保留`/1`允许的MODE_V2、bounded-review-64k/1及evaluation组合，仍拒绝ordinary/review_contract混用。无标记和`/1`历史解释不变；格式不授予生产、默认或模型资格。Python控制器按原construct/completion生成对象帧wire，固定reader验证raw/wire双摘要及重组关系；短程序只转发JSON.stringify帧和summary，无模型转录SHA算法。bundle≤64000、raw≤65536、wire≤196608、grant≤524288字节，50000 inner输出预算、单Code Mode/reader/reservation、原有限重试不变。实际PROGRAM、完整通知集合、每项真实宿主metadata预算、complete与final顺序仍严格验证。

`CONTEXT_WIRE_DELIVERED`一个新版本事件同时派生raw兼容投影与wire绑定，旧交付事件不能建立`/2`事实；proof使用`desktop-tool-surface/3`并重新读取原始transcript与grant。未知版本、错摘要、错call、字段/长度漂移拒绝，不补判旧失败。

`research_seed.recover_spawn_intent`只恢复原已准入stage的派发元数据，不spawn、不退款、不授新reader权限。父原生记录通过sessions下原路径、device/inode/header以及指定完整行的offset/length/hash绑定；允许之后追加，拒绝原区间改写、截断、换文件。created需原spawn call/result与同child原始header，沿原索引/身份/receipt幂等补齐；没有reservation的created拒绝。只有Start、无结果、一般error或未有真实否定证明均UNKNOWN，继续RECOVERY_REQUIRED。当前宿主无核验过的not-started结果格式，故不从异常推断未创建、不释放额度。历史已关闭账本不重新派发/升级。证据为逻辑来源核验，不是系统只读隔离或管理员篡改保护。
