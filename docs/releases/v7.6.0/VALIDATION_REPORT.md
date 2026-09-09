# V7.6.0 验证报告

证据按层区分。版本更新前的最终实现候选通过 Linux 完整包验证（284 项包测试与 142 项运行时测试）。当前 Windows 账户两次完整验证均超过原有运行时测试组 900 秒上限；两个互不重叠的运行时分组通过。超时仍记为失败，不能写成 Windows 全量通过；平台专项跳过不算该平台覆盖。

最终自然任务主样本 11/11 通过业务与受保护输入检查；流程为 10 PASS、1 项 OUTSIDE_SCOPE 阻断。另一次过期索引回放通过，不替换被阻断样本。两个独立新任务从账户安装版经 CLI 与 Desktop 二进制加载，验证初扫、后续复用、能力 ID 保持以及变更后旧回执失效。这只证明限定样例，不保证所有项目稳定复用，也不证明已打开 Desktop 会话热加载。

真实源码的隔离离线试用复用了前端、后端及 Provider 既有接口，通过类型、构建、渲染与后端断言。超大锁文件仍保留 CONTEXT_UNCONFIRMED；该试用没有将真实业务源码发给模型。此前一次合成探针意外到达模型服务，准确载荷保持 UNKNOWN，原“零模型调用”结论已撤回。

逻辑只读独立复审发现已修复；后续证据核对由主协调者完成，不冒充另一次独立复审。尚未证实净 Token 节省、P95 改善或成本收支平衡点。

以上观察发生于版本元数据更新前。V7.6.0 最终包、Windows/Ubuntu 兼容矩阵、可复现制品、账户加载、公开 Release 与 Pages 部署必须按精确提交和版本分别读回。[标签工作流](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/actions/workflows/release.yml)、[公开发行页](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/releases/tag/v7.6.0)及六项已核验制品提供发布证据；本文不预先宣称这些操作成功。

[发行说明](RELEASE_NOTES.md) · [审计报告](AUDIT_REPORT.md) · [验收规程](../../COMPONENT_REUSE_ACCEPTANCE.md)。

V7.6.0 候选随后通过 Linux 规范完整验证：284 项包测试与 142 项运行时测试，运行期间源码与快照哈希均保持一致。实际生成的[包验证报告](PACKAGE_VALIDATION.json)替换明确标记为 PENDING 的初始记录。后续仅修正文档并保留兼容注册表原有行尾；最终提交仍由 CI 独立验证。
