# Codex 跨项目长期技术助手 V6.3 验证报告

## 验证对象

- 版本：6.3.0
- 目标宿主：Windows 原生 Codex CLI 0.150.1
- 推荐形态：账户级 Plugin
- 升级基线：V6.1.0、V6.2.0
- 事件契约：TaskOutcomeEvent 2.0
- 自动子 Agent 上限：`gpt-5.6-terra + high`
- 执行授权：`NONE`

## 包内验证

| 项目 | 当前结果 | 证据入口 |
|---|---|---|
| JSON/TOML 解析与 Python 编译 | PASS | `scripts/validate-v63.py` |
| 中性语言与结构语义 | PASS | `scripts/semantic-lint.py` |
| Skill 路由用例 | PASS，35 条 | `scripts/routing-eval.py validate` |
| 包级单元与回归 | PASS，53/53 | `tests/test_*.py` |
| 共享 Runtime 回归 | PASS，6/6 | `runtime/tests/test_*.py` |
| 安装事务与故障注入 | PASS（定向） | `tests/test_package_manager_security.py` |
| 生命周期与自观察质量 | PASS（定向） | `tests/test_v60_deterministic_observation.py` |
| 确定性 ZIP 与发行证明合同 | PASS（定向） | `tests/test_v63_release_delivery.py` |
| Evolution Proposal 安全边界 | PASS（定向） | `tests/test_v51_controlled_evolution.py` |

`validate-v63.py` 的 PASS 字段均来自本次实际执行的命令与测试集；未执行的真实宿主项目保持 `NOT_EXECUTED`，不以常量替代证据。

## 隔离实机升级闭环

已在短路径隔离账户根执行真实 Codex CLI 0.150.1：

```text
V6.1.0 installed/enabled
  -> V6.3.0 install + verify + Plugin list readback
  -> V6.3 uninstall
  -> V6.1.0 installed/enabled restored
```

结果：PASS。

- V6.3 读回：installed=true、enabled=true、version=6.3.0；
- 卸载后读回：installed=true、enabled=true、version=6.1.0；
- V6.3 提交后活动事务日志不存在；
- 隔离升级备份保留；
- 正式账户 `CODEX_HOME` 未在该隔离测试中写入。

首次隔离尝试使用深层工作区路径，被 V6.1 的旧长路径限制阻断；该次未进入 V6.3 写入。短路径隔离复测通过。

## 独立复审

实施前复审识别发行证明、真实生命周期、可复现 ZIP、观测完整率和 Reviewer 归因门禁。实施后两类逻辑只读 Reviewer 检查状态/并发与测试/交付。

已修复的主要发现：

- 安装、仓库安装和卸载逐目标持久化 journal ownership；
- 卸载注销前持久化 Plugin 与 Marketplace 状态；
- Plugin Marketplace 在完整 staging 后按目标替换，并在替换前记录预期哈希；
- 生命周期按 `session_id + task_id` 聚合，跨 session task 冲突进入证据门禁；
- 重复 event_id 不再遮蔽后续链损坏；
- 事件锁不会仅因过期阈值删除仍存活进程的锁；
- 校验报告的测试数量和 PASS 状态从实际输出派生；
- V6.3 发布与审计文件纳入包结构。
- 发行证明覆盖证据内容篡改、非法路径、HMAC 正误密钥和生命周期跨 parent 顺序错误。

复审为逻辑只读。TaskOutcomeEvent 读回显示 Reviewer 实际模型为 `gpt-5.6-luna`；实际推理强度未由宿主事件提供，保持未验证。

## 正式宿主验收

Windows 原生 Codex CLI 0.150.1 的正式账户验收结果：PASS。

- V6.1.0 → V6.3.0 Plugin 事务升级成功；
- `codex plugin list --json` 精确读回：installed=true、enabled=true、version=6.3.0；
- 10 个 Skill、7 个 Reviewer、6 个 Hook 可发现；Reviewer TOML 未写死模型；
- 主配置哈希保持不变，升级前的账户 Skill 全部保留；
- 历史 project-context 文件数量未减少，升级备份保留；
- 活动事务标记不存在，目标目录均不是 Junction、Reparse Point 或符号链接；
- 新建只读验收任务并实际启动一个 `cp_review_test_delivery` Reviewer；
- Reviewer 实际模型为 `gpt-5.6-luna`；主 Agent 模型配置未修改；
- 同一会话严格产生 TURN_OPENED、SUBAGENT_STARTED、SUBAGENT_STOPPED、TASK_COMPLETED、SESSION_ENDED；
- TaskOutcomeEvent 2.0 共 5 条，哈希链连续，`project_id + repo_fingerprint` 匹配；
- SessionEnd 在 3 秒 Hook 限制内完成；Windows Hook 使用 `cp_hook.cmd`，不依赖额外 `python3.exe`。

正式 ZIP 的 SHA-256、两次字节一致构建、上述宿主证据哈希及篡改验证由包外机器证明绑定。机器证明不存在或验证失败时，不得把对应发行制品判定为已验证。

## 安全边界

- `execution_authorization=NONE`；
- 不自动修改 Skill、Reviewer、主 Agent 模型或业务代码；
- 不自动接受或实施 Evolution Proposal；
- 不自动提交、推送、部署、重启或操作生产环境；
- 项目聚合同时校验 `project_id + repo_fingerprint`；
- 历史 Event、Snapshot、Assessment、Proposal 与升级备份不随普通升级或卸载删除。
