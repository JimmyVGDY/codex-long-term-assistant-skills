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
