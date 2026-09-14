# V7.10.0 验证报告

当前报告绑定目标版本 `7.10.0`。package-only 定向与完整本地验证已完成；远端 CI、候选制品来源证明、隔离安装、真实新进程和公开 Release 仍需 S8/S9 读回。

必验边界：

- P1-01/P1-02 的状态分类、能力可用性、结构化动作和旧字段/退出码兼容；
- P1-03 的四条场景路径、帮助、中文/英文文案和统一入口参数；
- P2-01 的源码树、中文 ZIP、英文 ZIP、无 Python 基础入口及旧入口兼容；
- P2-02 的 Profile/State、旧 Markdown、显式 Evidence、仓库变化、预算、冲突和只读不变性；
- P2-03 的确定性包装层基准、失败样本、fixture 绑定和隐私白名单。

本地已确认：450 项 package tests、212 项 runtime tests（1 项 skip）；payload 236 文件，digest `8ee104982604c3e8b81d68530d5607202f255ddbb459a338e5ade36e4e695561`；中英文 ZIP 各 572 条目且两次构建字节一致。中文 ZIP SHA256 为 `f258466bda79b659bce96a45a1d3bc6fb6bdd89c8e3231139273cdd8809bb2c7`，英文 ZIP SHA256 为 `adc5217723675d398146e6fcd7f276ecc8b23b77820be418f4db8222d8e8bdc9`。

基准记录了 `simple-local-fix` 与 `cross-task-resume` 各 20 对 wrapper-only 样本；当前结果均为成功样本，但 resume 包装层中位耗时增加，不能据此宣称真实 Agent 成本下降。真实 Agent 样本、业务验收和宿主动态注册仍未验证。

独立复审：两轮、3+2 个 Reviewer，当前 packet `cad253d578449558b445c0209df9c25f22501486f6983326e0f11d5b10ec9da7`；结论为 logical-readonly、有非阻塞未验证项，第一轮阻塞问题已修复并有定向回归。

`RELEASE_COMPLETE` 与 `INCIDENT_EFFECTIVE` 继续分别核验；没有真实当前 Desktop 会话或业务项目证据时，不报告已加载或业务生效。当前报告不构成公开发布完成证明。
