# 多 Agent 单写者与事件型文档更新

## 九、多 Agent 单一写入者机制

### 9.1 主协调 Agent

只有主协调 Agent 可以更新共享：

- `CURRENT_TASK.md`；
- `PLAN.md`；
- `PROGRESS.md`；
- `DECISIONS.md`；
- `HANDOFF.md`；
- `KNOWN_ISSUES.md`；
- `DELIVERY_RECORD.md`。

### 9.2 子 Agent

子 Agent：

- 只返回结构化结果；
- 或写入主协调 Agent 明确分配的独立文件，例如：

```text
reviews/TASK-XXX/round-01/security.md
```

- 不直接修改共享任务文档；
- 不覆盖其他 Agent 记录；
- 不把内部推理写入文档。

### 9.3 Reviewer 隔离状态

共享任务状态必须记录：

- Reviewer TOML 的配置声明；
- 父会话实际沙箱；
- 当前隔离等级：`system-readonly` / `logical-readonly` / `self-review` / `unknown`；
- 是否要求严格只读；
- 是否满足严格只读资格；
- 隔离证据文件或受控探针结果。

不得把“Reviewer 没有写文件”或 TOML `read-only` 声明写成系统隔离通过。父会话可写时，默认记录为 `logical-readonly`。

### 9.4 多 Agent 检查点

采用事件合并，至少在以下四个可恢复节点持久化：

1. 审查包、Reviewer 计划、模型档位和预算确定，且第一轮已派发；
2. 本轮结果收齐并完成根因归并；
3. 集中修复和受影响验证完成；
4. 最终定向复核和门禁结论形成。

派发一个 Reviewer、收到一个中间结果或重复读取状态本身不单独写检查点；发生阻塞、授权变化或高风险操作时仍立即写入。

---

## 十、事件型文档更新

### 10.1 计划变化

更新 `PLAN.md`：

- 阶段增加、删除、阻塞或回滚；
- 依赖变化；
- 验证、复审、灰度或回滚方式变化；
- 用户调整目标或范围。

### 10.2 关键决策

更新 `DECISIONS.md`：

- 背景和已确认事实；
- 候选方案；
- 选择原因；
- 影响、兼容、性能和成本；
- 风险、防御和回滚；
- 重新评估条件。

### 10.3 范围外问题

更新 `KNOWN_ISSUES.md`，明确证据等级、影响和暂不处理原因，不擅自扩大任务。

### 10.4 交接或暂停

更新 `HANDOFF.md`，形成可让不了解历史聊天的新 Agent 恢复的最小完整快照。

### 10.5 形成实际交付

更新 `DELIVERY_RECORD.md`，记录实际交付、测试、复审、CHANGELOG、Commit、推送、部署、重启、生效和遗留风险。

临时实验、无行为变化格式调整和已回滚未交付尝试不进入正式交付记录。

---
