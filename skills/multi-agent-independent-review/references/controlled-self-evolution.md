# 受控自进化按需参考

本 Skill 只负责在明确触发时调用统一 Evolution Runtime，不维护第二套合同。

权威资料：

- `runtime/cp_runtime/evolution/manifest.json`
- `docs/evolution/SELF_EVOLUTION_ARCHITECTURE.md`
- `docs/evolution/CONTROLLED_EVOLUTION_OPERATIONS.md`

强制边界：

1. 先 Dry Run；
2. 数据不足不提案；
3. Proposal 的执行授权只能是 NONE；
4. ACCEPT 只记录人工决策；
5. 实施必须另建任务并重新审批；
6. 不得自动修改或删除任何 Skill、Reviewer、模型配置和业务代码；
7. JSONL 或哈希链损坏时失败关闭。
