# Proposal Lifecycle V6

推荐状态：

`PENDING_REVIEW -> ACCEPTED/REJECTED/DEFERRED -> IMPLEMENTATION_LINKED -> VALIDATION_RECORDED -> CLOSED`

也允许 `SUPERSEDED` 关闭被新证据取代的提案。

硬边界：

- `execution_authorization=NONE` 永久保持不变。
- ACCEPT 后必须建立新的实施 Task，并重新获取该任务需要的授权。
- 实施必须绑定 Git Baseline；验证阶段绑定 Commit/工作树状态与 Evidence。
- REJECTED 提案在证据摘要、策略版本和观察窗口都没有实质变化时不得机械重生。
