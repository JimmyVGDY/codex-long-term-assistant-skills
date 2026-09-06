# V7.5.0 验证报告

2026-09-06，本地版本固定后的完整验证通过：276 package + 6 runtime。包验证涵盖语义、隐私、路由、载荷身份和工作树无副作用门禁；双语覆盖与链接检查均为 0 项问题。

新增验收覆盖任务反馈与终态合并、普通仓库与 linked worktree 身份、观察健康、增量并发和崩溃恢复、异常变化触发、跨账本场景统计、实施任务样本隔离、收益不足/支持/回归边界，以及根因候选和回归跟踪篡改拒绝。

两轮实施后逻辑只读独立复审已完成：六项确认问题集中修复并复核通过；一次不可变定稿的契约经澄清后获复核认可。未取得操作系统只读隔离证明，未激活宿主 DelegationBudget 预占门禁。

Windows 账户 Plugin 已安装到 7.5.0，Codex CLI 0.153.4 的版本、启用状态和载荷读回通过。安装目录中的验证入口与 Hook 在隔离项目中通过 UserPromptSubmit → validate-task → finalize-task → Stop 关联，以及 SessionEnd 封印后显式启用的增量分析。该证据不等于真实 LLM 父子 Agent 的完整宿主旅程。

Plugin 载荷：192 个文件，SHA-256 `11742fa17f56a3f241cbb6bb2a83c3bc7acde11ae74403841ab41769fc269eba`。

包级结果见 [PACKAGE_VALIDATION.json](PACKAGE_VALIDATION.json)。真实项目的优化收益仍需独立实施任务及至少 7 天、每组至少 5 个独立任务的有效观察证据；本发布未宣称真实项目收益已获证实。自动化默认关闭，提案永久保持 `execution_authorization=NONE`。

本报告记录提交前本地证据。远端提交、Windows/Ubuntu 11 版兼容矩阵、CI、标签、正式 Release、ZIP 校验和与构建来源证明以对应发布工作流和发行附件为准；本报告不预先宣称这些动作成功。实际账户卸载/回滚未执行，已保留安装器事务备份。
