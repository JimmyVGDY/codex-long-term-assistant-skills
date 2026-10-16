# Skill 路由回归测试说明

## 目的

验证主 Agent 是否遵守“一个主领域 Skill、最少辅助 Skill、按阶段延迟激活”的规则，防止新增 Skill 后出现过度加载或错误加载。

## 文件

- 用例：`tests/skill-routing-cases.json`
- 工具：`scripts/routing-eval.py`

每条用例包含：

- `required`：必须激活；
- `optional`：只有实际项目内容需要时才激活；
- `forbidden`：当前请求不应激活；
- `max_active`：最大活动 Skill 数量。

当前用例集包含受控演进的跨任务收益、成本校准和提案正例，以及普通修复、独立复审、长期任务的反例。实际数量由用例文件读取。

## 分阶段观察与例外

`phases` 是 schema 1 的可选扩展：每个阶段有独立 `id`、`required/optional/forbidden` 和 `max_active`。观察中的 `phases` 逐阶段记录 `activated` 与 `exception_reason`；顶层 `activated` 是阶段并集，不代表这些能力同时加载。缺失阶段、重复阶段、阶段并集不一致或违反阶段边界均不通过。

同阶段超过三个能力须给出非空必要性说明，且仍不得超过该阶段上限或激活 forbidden。无 phases 的旧用例继续解析；若实际激活超过三个，同样须在观察的 `exception_reason` 说明原因。提高 `max_active` 本身不构成豁免。

真实宿主观察仍使用 schema 2。原始最终报告除现有标记外，分阶段观察包含一行 `PHASE_OBSERVATIONS=<JSON数组>`；非分阶段的超额说明使用 `ACTIVATION_EXCEPTION_REASON=<单行说明>`。评分器核对报告字节摘要和这些字段，禁止事后手工补理由。它验证的是宿主最终报告，不是独立路由 trace。

## 执行

```bash
python3 scripts/routing-eval.py validate
python3 scripts/routing-eval.py list
python3 scripts/routing-eval.py make-template --output routing-observations.json
```

在实际 Codex 会话中逐条执行 Prompt，将实际激活 Skill 写入 `activated`。不得查看期望后人工补齐结果。

```bash
python3 scripts/routing-eval.py evaluate --results routing-observations.json
```

## 通过标准

- required 全部出现；
- forbidden 全部不出现；
- 活动 Skill 不超过 `max_active`；
- optional 不作为强制通过条件。

## 限制

Codex 是否展示完整隐式 Skill 激活信息取决于当前客户端能力。无法直接观察时，可让主 Agent 在测试模式下仅报告激活计划，不执行任务。该报告仍属于模型输出，不能替代对实际工作行为的抽查。

## 隔离与模型路由用例

路由集新增：

- 严格只读复审：必须加载 `multi-agent-independent-review`，先检查父会话权限；
- 可写父会话中的逻辑只读复审：必须明确 `logical-readonly`，不能把 TOML 声明当作系统隔离。

新默认按脚本选择 GPT-6 Luna、Sol、Astra 的 low/medium/high；机械任务优先 Luna/low，普通或信息不足采用 Sol/medium，多个 Skill 不自动累加强度。历史模型组合只用于旧记录回放。

路由测试只验证 Skill、批准派发档位与计划选择，不能证明沙箱权限；宿主实际模型身份不属于 Agent 的输入、证据或验收范围。

## 独立的开发集与最终集

新增 tests/skill-routing-study-cases.json 与 scripts/routing_study.py，保留原 52 条用例、旧观察格式和评分规则。新集包含文档、设计、浏览器、MCP 四组，每组 3 条正例和 3 条近邻负例；16 条开发、8 条最终验收，意图族不能跨集合。关键案例重复 3 次，本批合计每个版本 40 次、双版本 80 次，实际数量由准备命令读回。

在 Plugin 源码仓库中执行准备；案例执行仍通过 Codex Desktop。这些是内部管理与验证工具，不是独立 CLI 产品轨道。

~~~text
python scripts/routing-eval.py prepare-study --baseline v7.16.2 --environment <environment.json> --output <new-external-directory>
~~~

environment.json 固定六个字段：platform、runtime、requested_model、requested_effort、permissions_digest、cache_condition。记录实际使用的环境和请求参数；permissions_digest 是本轮明确授权边界的规范化 SHA-256，不代表系统隔离。使用 --locale en 选择英文样例及英文 Skill 入口快照。准备不调用模型，也不产生派发、文件或生产操作权限；实际执行前先核对任务预算和权限。

study.json 冻结集合、两个版本的 Skill 入口摘要、环境、重复次数与每次输入。prompts 下的请求只含不透明试验 ID 和原始问题，不含期望 Skill。执行者不读取 suite.json、study.json、另一版本产物或答案字段。目录分离是逻辑隔离，不能冒充沙箱。默认候选取当前工作区；--candidate 可固定提交。

每次记录一份既有 schema 2 宿主报告。新研究只接受 codex_desktop_task；旧格式中的 CLI 来源仅为历史读取保留。原始报告还须含唯一 TRIAL_ID 和 INPUT_SHA256 标记，宿主读回须含 RULE_DIGEST、ENVIRONMENT_DIGEST，分别匹配冻结输入、规则和环境。记录真实 task_id，不把同一任务的重放算成独立样本。

在同一已安装宿主中仅比较冻结规则的路由计划时，报告增加 `rule_context`：`kind=frozen_snapshot_plan`，并填写冻结规则的 `plugin_version` 与 `rule_digest`。宿主读回另含 `RULE_CONTEXT=frozen_snapshot_plan` 和 `RULE_PLUGIN_VERSION=<冻结版本>`；`host.plugin_version` 始终是实际安装版本。既有报告未提供此显式模式时继续要求安装版本匹配规则版本。此模式仅证明真实 Desktop 中对冻结输入的路由计划自报，不证明历史包已安装或自动加载器行为。

每个集合单独保存索引：

~~~json
{"schema":"routing-study-results/1","study_digest":"<study.json record_digest>","runs":[{"trial_id":"<opaque trial ID>","results_file":"runs/example/result.json","evidence_dir":"runs/example/evidence"}]}
~~~

~~~text
python scripts/routing-eval.py evaluate-study --study <study.json> --results <development-index.json> --split development --output <new-report.json>
python scripts/routing-eval.py evaluate-study --study <study.json> --results <final-index.json> --split final --output <another-new-report.json>
~~~

评分复用旧宿主合同，并按版本和组分别输出漏触发、误触发、过量加载与阶段错误。缺观察为 PARTIAL；真实错误为 FAILED。报告保留后命令返回非零，不能用退出成功冒充验收通过。证据读取受文件、总字节、路径及链接边界限制。

最终集合不能用于反复调参；泄露或用于选描述后重建独立集合，保留旧结果。工具不自动修改描述，也不把小样本计数判为收益。实际路由轨迹未知、真实费用未知和收益 UNKNOWN 均保留；宿主最终自报不是独立签名的路由轨迹。
