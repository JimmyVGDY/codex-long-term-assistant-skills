# V6.6 包内验证报告

版本：6.6.0  
状态：包级验证通过；真实安装与生命周期证据在包外升级报告记录

## 验证范围

- Python 语法、JSON、TOML 和语义门禁。
- 10 个 Skill、7 个 Reviewer、6 个 Hook 和 SessionEnd timeout=3。
- Windows spawn 多进程事件写入与 keyring 轮换。
- 强制终止后的 OS 锁释放。
- keyring 临时文件 fsync、replace 前后断点。
- SessionEnd 签名入列、worker claim/append/seal/ack 恢复和 event_id 幂等。
- Reviewer 校准 V2。
- 非破坏归档、容量预算、项目双重绑定和健康概览隐私投影。
- Plugin 安装事务、回滚、payload 身份和确定性 ZIP。

## 已执行结果

- Package tests：92/92 PASS。
- Runtime tests：6/6 PASS。
- V6.6 深化专项：17/17 PASS。
- Payload：170 files，digest `2251421c9350e29022662a784cf1ef7bb98f4f36de4b0775a751c6f1b0e92885`。
- Semantic lint：PASS。
- 实施前 Reviewer：2；实施后 Reviewer：2；定向复核：2；阻断根因全部关闭。
- Windows 空格路径六 Hook、Junction/reparse、PID 复用、seal old-or-new 发布和 SessionEnd 失败诊断均有运行测试。

## 模型证据口径

- `requested_model_policy`：由 PreToolUse 正反用例证明。
- `runtime_model_evidence`：只有可信宿主证明通过时为 VERIFIED。
- `diagnostic_model_observation`：只保存诊断旁证，不参与 VERIFIED 判定。

Codex 0.150.1 的预期实际值为 `PASS / UNAVAILABLE / <diagnostic observation>`。

## 安全边界

- 事件、归档、队列和健康概览不保存 Prompt、完整回答、代码正文、Diff 或凭据。
- 归档只复制已关闭 segment，不移动 canonical 链，不自动删除历史。
- 项目聚合继续同时校验 `project_id + repo_fingerprint`。
- Proposal 保持 `execution_authorization=NONE`。
