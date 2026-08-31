# V5.1 自观察与受控自进化版发布说明

## 新增

- 结构化 Self Observation；
- 确定性 Value/Complexity Analysis；
- Optimization Proposal；
- Proposal/Decision 追加式哈希链；
- 人工 ACCEPT/REJECT/DEFER；
- 提案去重、数据脱敏、路径隔离和失败关闭；
- V5.1 CLI、策略文件、专项测试和操作文档；
- 安装后 `${CODEX_HOME}/tools/evolution.py` 独立入口。

## 保持不变

- 原 9 个 Skill 与 7 个 Reviewer；
- V5.0 项目治理、Approval、Evidence、Checkpoint、Memory 和 Finalization；
- 模型分级与 Reviewer 成本控制；
- 原有安装、验证、Doctor、备份和 Restore 流程。

## 安全边界

V5.1 没有自动执行、自我改写或自动接受能力。所有提案的 `execution_authorization` 固定为 `NONE`。
