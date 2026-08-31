# V6.2 验证报告

验证日期：2026-08-28  
目标宿主：Windows 原生 Codex CLI 0.150.1  
Python：3.13.15

## 结论

V6.2 源码、安装事务、Plugin 注册、V6.1 升级恢复、Windows 长路径兼容和治理安全边界均通过验证，可生成正式发行包。

## 静态与自动化验证

- 语义校验：通过；10 Skills、Plugin/Hooks、账户 Skill 目录、模型上限和受控演进边界一致。
- 中性语言门禁：自然语言文件中未发现具体姓名、第一或第二人称、对话化主体词及本机身份路径；机器契约保持不变。
- 路由用例：35/35 通过。
- 单元与回归测试：27/27 通过。
- Package 验证：通过；版本 6.2.0、10 Skills、7 Reviewers、6 Hooks、TaskOutcomeEvent 2.0。
- Windows 超长路径：连续两次 Plugin 安装、备份清单、验证、两次卸载恢复原始状态通过。
- Junction/Reparse Point：拒绝覆盖测试通过。
- 外部文件保护：卸载保留安装前和安装期间新增的非受管 AGENTS 内容、自定义 Hook 与 hooks.json 元数据；旧版受管区块/Hook 可恢复，marker 文字冲突不误删，畸形 hooks.json 失败关闭且不覆盖。
- Hook：UTF-8、中文截断 Stop、跨平台 Windows launcher、SessionEnd timeout=3 秒通过。
- 模型门禁：Luna Low/Medium、Terra Medium/High 允许；Terra xhigh/max、Sol、未知模型和未来 Terra 名称拒绝。

## Codex 0.150.1 真实隔离升级

在独立 `HOME`、`USERPROFILE` 和 `CODEX_HOME` 中完成：

1. 安装并验证 V6.1 Plugin；
2. 执行 V6.2 dry-run；
3. 正式升级并执行 `verify`；
4. 读取 `codex plugin list --json`；
5. 确认 V6.2 为 `installed=true`、`enabled=true`、`version=6.2.0`；
6. 正常卸载 V6.2，确认 V6.1 文件、状态和 Plugin 注册恢复；
7. 清空一次性隔离注册。

升级备份清单存在且可读。测试前后真实账户环境中的 V6.1 状态文件与 `config.toml` SHA-256 均未变化，实际 Plugin 仍为 V6.1、installed/enabled 均为 true。

## 安全与数据边界

- `execution_authorization=NONE`。
- 不自动修改 Skill、Reviewer、模型路由、AGENTS 受管区块以外内容或业务仓库。
- 不自动接受或执行 Evolution Proposal。
- 不自动提交、推送、部署、重启或操作生产环境。
- V6.1 历史项目上下文、Event、Snapshot、Assessment、Proposal 和 Decision 不迁移、不删除。
- 自观察聚合同时校验 `project_id + repo_fingerprint`；事件链使用 SHA-256 并验证连续性。

## 已知说明

历史 V6.1 卸载器本身不支持极端长路径；V6.2 安装器已向后兼容读取并恢复 V6.1 状态。在一次性超长路径测试的最终清空阶段使用 V6.2 卸载器执行，正式 V6.2→V6.1 恢复阶段未使用 `--force`。
