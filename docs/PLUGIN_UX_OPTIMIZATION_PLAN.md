# Plugin 安装即用与低成本优化计划

English: [Implementation plan](PLUGIN_UX_OPTIMIZATION_PLAN.en.md)

## 当前状态

本计划从 V7.8.1 开始实施。基础 Plugin 的目标是无需 Plugin 专属 Python、Profile、索引、台账或 Hook 即可安装并开始普通工程任务；增强能力在需要长期任务、索引、受控写入或硬预算时单独接入。

基础能力不等于放宽授权、降低项目测试门槛，或绕过已启用的安全控制。安装、注册、当前任务加载和业务验收分别记录。

## 分层契约

| 组件 | 内容 | 依赖 | 可见结果 |
| --- | --- | --- | --- |
| base | 10 个 Skill 与入口元数据 | Codex Plugin 宿主 | 通过 `install-base.ps1` / `install-base.sh` 安装后可直接描述任务 |
| enhanced | Hook、Python runtime、账户级工具、Reviewer、全局受管规则 | Python 3.11+ 与已验证宿主契约 | `install-user` 在同一产品上接入长期记忆、索引、预算和受控写入 |
| strict controls | 已启用门禁、Required 预算等 | enhanced 的等价执行控制 | 受控操作失败关闭 |

base 与 enhanced 使用同一 Skill 规则源，不能形成两套工程规范。增强组件不提供重复 Skill，避免宿主发现两份同名 Skill；基础入口遇到已受管的增强 state 时拒绝降级，增强卸载则恢复其已知基础安装。

## 安全与迁移决策

1. 已启用 capability gate、Operation v2 或 Required 委派预算时，拒绝移除 enhanced；不能把基础模式作为绕过写入控制的途径。
2. 旧 V7.8.1 完整 Plugin 迁移为 `enhanced`，保留现有状态、备份、未知资产和 OFF 偏好。
3. 每个组件必须有独立 payload digest、受管目标、备份标签和卸载所有权；base、enhanced 和未知资产不能相互删除。
4. `doctor` 的默认摘要固定回答：当前可做什么、受影响功能、原因、唯一下一步；`--json` 保持机器可读细节。
5. 未验证 Hook 契约的宿主仍可使用 base；涉及 Hook 的能力必须显示未启用或不可用，不能报告完整兼容。

## 实施顺序与验收

1. 建立 base/enhanced 清单、状态 schema 和构建制品矩阵。
2. 改造安装、verify、inventory、recover、uninstall 与旧状态迁移。
3. 在隔离账户验证全新 base、base 到 enhanced、旧完整 Plugin 升级、增强卸载、回滚和中断恢复。
4. 落实 LIGHT 默认串行执行、有效证据复用和人类可读诊断。
5. 更新中英文 README、安装指南、CHANGELOG 和发行材料，完成跨平台与真实宿主验收后发布。

最低安全验收：在已启用门禁但宿主没有可验证 Operation v2 起点时，`apply_patch`、`Edit` 与 `Write` 必须仍拒绝；基础能力只能继续不受该控制约束的普通任务。
