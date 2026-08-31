# Codex 跨项目长期技术助手 V6.4 验证报告

## 验证对象

- 版本：6.4.0
- 目标宿主：Windows 原生 Codex CLI 0.150.1
- 推荐形态：账户级 Plugin
- 升级基线：6.1.0、6.2.0、6.3.0
- 事件契约：TaskOutcomeEvent 2.0
- 自动子 Agent 上限：`gpt-5.6-terra + high`
- 执行授权：`NONE`

## 候选包验证

| 检查项 | 当前结果 | 证据入口 |
|---|---|---|
| 包级单元与回归 | PASS，67/67 | `python -m unittest discover -s tests -v` |
| 共享 Runtime 回归 | PASS，6/6 | `python -m unittest discover -s runtime/tests -v` |
| 中性语言与结构语义 | PASS | `scripts/semantic-lint.py` |
| 受管树嵌套 Reparse 防护 | PASS | `test_nested_reparse_inside_managed_plugin_tree_is_rejected` |
| Plugin 硬崩溃恢复 | PASS | `tests/test_package_manager_security.py` |
| 事件半记录恢复与跨段连续性 | PASS | `tests/test_v64_resilience.py` |
| 非法终态与非法 schema 失败关闭 | PASS | `tests/test_v64_resilience.py` |
| actual_model 精确允许列表 | PASS | `tests/test_v64_resilience.py` |
| 统一发行验证器合同 | PASS | `tests/test_v64_release.py` |
| 确定性 ZIP 与 attestation 合同 | PASS | `tests/test_v64_release_delivery.py` |
| Hook 未暴露模型时的关联宿主会话验收 | PASS | `test_lifecycle_uses_correlated_host_session_model_without_rewriting_hook_facts` |

包级完整回归于 2026-08-28 执行，最终测试数为 67；Runtime 回归为 6。正式机器证据记录实际命令输出与耗时。

## 独立复审

实施前两路 Reviewer 检查状态并发与兼容回归；实施后第一轮两路 Reviewer 检查安全边界与测试交付。第一轮共识别 3 项阻断、1 项非阻断：

- 显式非法终态不得降级为 UNKNOWN；
- 哈希自洽但 schema 非法的已有事件必须拒绝；
- actual_model 必须采用精确允许列表；
- 受管树内部链接型后代必须在递归操作前拒绝。

四项均已修复并新增回归。第二轮复用新冻结包定向复核，原发现全部关闭，未产生残留发现。Reviewer 运行隔离级别为 logical-readonly；第二轮实际模型与推理强度未由宿主证据确认，状态保持未验证。

## 正式制品与宿主状态

以下项目在正式 ZIP 构建和真实账户升级前保持未验证：

| 检查项 | 当前结果 |
|---|---|
| 两次干净构建字节一致 | NOT_EXECUTED |
| 正式 ZIP SHA-256 | NOT_EXECUTED |
| V6.3 → V6.4 真实账户升级 | NOT_EXECUTED |
| Plugin installed/enabled/version=6.4.0 | NOT_EXECUTED |
| ZIP/Marketplace/cache payload digest 一致 | NOT_EXECUTED |
| 10 Skill、7 Reviewer、6 Hook 实机发现 | NOT_EXECUTED |
| 新会话五事件生命周期 | NOT_EXECUTED |
| SessionEnd 3 秒兼容 | NOT_EXECUTED |
| 包外统一验证与 attestation | NOT_EXECUTED |

对应证据产生后，本报告再更新为最终状态。计划、代码存在或文件复制完成均不能替代真实宿主读回。

## 安全边界

- 不删除未知账户资产；
- 不改写 `config.toml` 或主 Agent 模型配置；
- 不写死 Reviewer 模型；
- 不自动修改 Skill、Reviewer、路由或业务仓库；
- 不自动接受或实施 Evolution Proposal；
- 不自动提交、推送、部署、重启或操作生产环境；
- 项目聚合同时校验 `project_id + repo_fingerprint`；
- 历史 Event、Snapshot、Assessment、Proposal 和升级备份持续保留。
