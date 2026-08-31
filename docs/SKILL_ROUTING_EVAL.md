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

Codex 是否展示完整隐式 Skill 激活信息取决于当前客户端能力。无法直接观察时，可要求主 Agent 在测试模式下仅报告激活计划，不执行任务。该报告仍属于模型输出，不能替代对实际工作行为的抽查。

## V4.2 隔离与模型路由用例

路由集新增：

- 严格只读复审：必须加载 `multi-agent-independent-review`，先检查父会话权限；
- 可写父会话中的逻辑只读复审：必须明确 `logical-readonly`，不能把 TOML 声明当作系统隔离。

路由集还应抽查：机械任务优先 Luna、业务判断使用 Terra、自动上限 Terra High、多个 Skill 不累加强度。

路由测试只能验证 Skill 与计划选择，不能证明子 Agent 的实际模型或沙箱权限；运行时信息必须由线程证据、结构化结果和隔离记录核验。
