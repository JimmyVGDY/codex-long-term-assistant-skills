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

路由集还应抽查：机械任务优先 Luna、业务判断使用 Terra、自动上限 Terra High、多个 Skill 不累加强度。

路由测试只验证 Skill、批准派发档位与计划选择，不能证明沙箱权限；宿主实际模型身份不属于 Agent 的输入、证据或验收范围。
