# V7.6.0 验证报告

当前实现候选通过 Linux 规范完整包验证：284 项包测试和 144 项运行时测试，运行期间源码与快照哈希一致。实际输出见[包验证报告](PACKAGE_VALIDATION.json)。随后仅整理本报告；最终发行的 Windows/Ubuntu 全量检查、双语可复现构建和 11 版本宿主矩阵，以[精确标签工作流](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/actions/runs/34304636222)和[公开发行制品](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/releases/tag/v7.6.0)为准。

首轮 PR CI 的两个 Linux 目标和宿主矩阵通过，Windows 运行时测试完整结束但出现短路径身份错误和非规范预期路径断言，并非超时。修复复用既有 safe_path 核验统一预算根路径，保留跨仓库拒绝和全部读取、超时预算。本机已通过全部失败路径的定向复验及新增真实 Windows 8.3 短路径回归。此前当前账户的两次 Windows 整包超时是另一批历史结果，不能改记为全量通过；平台专项跳过也不算该平台覆盖。

初始功能候选的自然任务主样本 11/11 通过业务与受保护输入检查，流程为 10 PASS、1 项 OUTSIDE_SCOPE 阻断；额外过期索引回放通过，不替换被阻断样本。两个安装版独立新任务验证初扫、后续复用、能力 ID 保持和变更后旧回执失效。这些有限样例不保证所有项目稳定复用，也不证明已打开 Desktop 会话热加载；正式版本的安装与新进程加载另行核验。

真实源码的隔离离线试用复用了前端、后端与 Provider 既有接口，通过类型、构建、渲染和后端断言；超大锁文件仍保留 CONTEXT_UNCONFIRMED，该试用没有将真实业务源码发给模型。此前一次合成探针意外到达模型服务，准确载荷保持 UNKNOWN，原“零模型调用”结论已撤回。

初始实现的逻辑只读独立复审发现已修复；发布期短路径修复及后续证据核对由主协调者完成，不冒充另一次独立复审。尚未证实净 Token 节省、P95 改善或成本收支平衡点。标签、公开 Release、Pages 部署、账户版本和实际加载均需分别读回，包验证不替代这些证据。

[发行说明](RELEASE_NOTES.md) · [审计报告](AUDIT_REPORT.md) · [验收规程](../../COMPONENT_REUSE_ACCEPTANCE.md)。

V7.6.0 发布后读回（核验时间：2026-09-09 04:04:02 UTC）：提交 `26d013fa824fa148a839d30aaedd22f3744e8bbf` 的[发行工作流](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/actions/runs/34304636222)、[主分支 CI](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/actions/runs/34304540318)和[文档站部署](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/actions/runs/34304540320)均通过。此记录绑定该标签及上述核验时间，不替代后续修改的验证，也不证明所有宿主都支持取消。
