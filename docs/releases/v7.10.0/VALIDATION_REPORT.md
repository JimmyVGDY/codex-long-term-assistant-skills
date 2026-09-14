# V7.10.0 验证报告

当前报告绑定目标版本 `7.10.0`。package-only 定向、完整本地验证、目标 ZIP 隔离安装及 Windows 原生基础/增强注册读回已完成；隔离账户没有认证，因此真实 Codex 任务、远端 CI、候选制品来源证明和公开 Release 仍需后续 S8/S9 读回。

必验边界：

- P1-01/P1-02 的状态分类、能力可用性、结构化动作和旧字段/退出码兼容；
- P1-03 的四条场景路径、帮助、中文/英文文案和统一入口参数；
- P2-01 的源码树、中文 ZIP、英文 ZIP、无 Python 基础入口及旧入口兼容；
- P2-02 的 Profile/State、旧 Markdown、显式 Evidence、仓库变化、预算、冲突和只读不变性；
- P2-03 的确定性包装层基准、失败样本、fixture 绑定和隐私白名单。

本地已确认：458 项 package tests、212 项 runtime tests（1 项 skip）；payload 236 文件，digest `8ee104982604c3e8b81d68530d5607202f255ddbb459a338e5ade36e4e695561`；中英文 ZIP 各 572 条目，二者均重复构建字节一致并通过 archive verify，最终 ZIP 的 SHA256/大小保留在仓库外交付记录以避免发行报告自引用。目标 ZIP 在短路径临时隔离环境中完成基础安装、增强安装、status/verify 及已安装 `cp-runtime.py` 与解压包统一入口的同目标 `resume`，两条入口均读回 `CURRENT`；隔离 `codex login status` 为 `NOT_AUTHENTICATED`，因此未执行需要认证的真实模型任务。

基准记录了 `simple-local-fix` 与 `cross-task-resume` 各 20 对 wrapper-only 样本；当前结果均为成功样本，但 resume 包装层中位耗时增加，不能据此宣称真实 Agent 成本下降。真实 Agent 样本、业务验收和宿主动态注册仍未验证。

独立复审：两轮、3+2 个 Reviewer，最终 packet `60ec3a5a8aa31a7a1cfb6dcdbefc5f5c88c7439d862b312c32bc071be8c46c45`；结论为 logical-readonly、有非阻塞未验证项，第一轮阻塞问题已修复并有定向回归。本修复提交需重新绑定后续交付证据。

`RELEASE_COMPLETE` 与 `INCIDENT_EFFECTIVE` 继续分别核验；没有真实当前 Desktop 会话或业务项目证据时，不报告已加载或业务生效。当前报告不构成公开发布完成证明。
