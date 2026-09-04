# V7.4 受控演进操作手册

> 状态：`active`。本页适用于 V7.4.2；Evolution 组件 Manifest 仍使用 `5.1.0` 合同版本，默认策略为 `v6.5-default-1`，两者都不是当前包版本。

## 1. 适用场景

仅在以下场景运行自进化分析：

- 明确提出分析长期失败、成本或流程问题；
- 完成一个版本、里程碑或事故复盘；
- 已积累至少 5 条记录和 3 个独立 Task ID；
- 需要评估模型分级、Reviewer 组合或 Skill 路由是否合理。

不要在每个普通任务结束后自动运行完整分析，避免额外上下文、状态噪声和无价值提案。

## 2. 推荐工作流

### 步骤一：检查项目身份

确认 `project_id` 与当前仓库、Remote、Branch 和 Project Profile 一致。发现项目串线时停止。

### 步骤二：只读 Dry Run

```bash
python3 -B scripts/evolution.py run \
  --project-id <project-id> \
  --context-root ~/.codex/project-context \
  --dry-run
```

检查：

- 实际读取了哪些 source files；
- 有多少记录缺少 Task ID；
- 时间窗口是否可信；
- 是否出现不应纳入的历史记录；
- 信号是否有足够独立 Evidence。

证据充足性按信号分别判断：模型升级需要实际模型覆盖，负面结果需要已知终态覆盖，路由偏差需要明确路由观察，Reviewer 收益需要可归因结果。一个信号缺少证据不会无条件阻断其他证据充分的信号。

### 步骤三：持久化提案

```bash
python3 -B scripts/evolution.py run \
  --project-id <project-id> \
  --context-root ~/.codex/project-context
```

相同 Fingerprint 的活跃提案不会重复创建。

### 步骤四：人工评审

逐项检查：

1. Evidence 是否真实支持问题；
2. 是否把相关性误当成因果关系；
3. 是否跨越项目或版本适用范围；
4. 是否遗漏特殊高风险场景；
5. 预期收益是否可测量；
6. 回滚与验证计划是否可执行；
7. 是否应该先补数据而不是修改规则。

### 步骤五：记录决定

使用 `decide` 记录 ACCEPT、REJECT 或 DEFER：

```bash
python scripts/evolution.py decide \
  --project-id <project-id> \
  --context-root <context-root> \
  --proposal-id <proposal-id> \
  --decision <accept|reject|defer> \
  --actor <human-actor> \
  --rationale "<至少十个字符的人工理由>"
```

### 步骤六：另建实施任务

只有 ACCEPT 后，才可以由另行取得授权创建实施任务。实施任务必须重新生成：

- Task Envelope；
- Git 基线；
- 修改范围；
- Approval；
- Review Packet；
- 回滚计划；
- 验收标准。

## 3. 典型信号与处理

| 信号 | 默认动作 | 禁止的捷径 |
|---|---|---|
| 重复失败 | MODIFY 候选 | 不得简单增加重试或扩大模型档位 |
| 模型频繁升级 | MODIFY 候选 | 不得把全部任务默认切到 Terra High |
| Skill 路由偏差 | MODIFY 候选 | 不得默认加载所有 Skill |
| 修复轮次过高 | MODIFY 候选 | 不得取消轮次上限 |
| Reviewer 低发现率 | INVESTIGATE | 不得根据少量样本直接删除 |
| 长窗口 Reviewer 零发现 | DEPRECATE 候选 | 仍需先降级观察，不得自动删除 |
| 非成功结果偏高 | INVESTIGATE | 不得在根因未分层前修改全局规则 |

## 4. 数据质量问题

以下情况只保留观察，不生成修改提案：

- 记录少于策略最小值；
- 独立 Task ID 不足；
- 只有单次失败；
- Reviewer 样本量不足；
- 时间字段没有时区；
- 只有聚合总数，没有可追溯 Evidence；
- 数据源损坏或哈希链异常。

## 5. 故障处理

### JSONL 损坏

停止分析，定位报错行，从可信备份恢复或修复源记录。禁止跳过坏行后继续。

### 哈希链失败

停止使用该注册表，从备份恢复；保留损坏文件用于审计。禁止重新计算哈希掩盖历史修改。

### 重复提案

系统会返回已存在的活跃提案。若旧提案已 REJECTED 且新 Evidence 发生实质变化，可以在新的观察窗口重新生成。

### 数据源过大

通过策略受控提高限制，或先生成脱敏聚合记录。不要让分析器无边界扫描项目目录。

## 6. 验证命令

```bash
python scripts/evolution.py validate \
  --project-id <project-id> \
  --context-root <context-root>
```

## 7. 明确限制

当前分析规则是确定性启发式，不等同于因果推断。它可以指出值得调查或优化的稳定模式，但不能替代人工理解业务背景、代码实现、生产风险和组织约束。
