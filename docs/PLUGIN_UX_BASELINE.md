# Plugin 安装体验与使用成本优化：S0 基线与分层决策

English: [S0 baseline and layering decision](PLUGIN_UX_BASELINE.en.md)

## 结论

本次优化的候选目标版本确定为 **V7.9.0**。采用一个 Marketplace、一个面向安装者的基础 Plugin 和一个仅在需要时启用的增强伴随 Plugin：基础 Plugin 保持既有 `codex-cross-project-engineering-assistant` 名称，增强伴随 Plugin 暂定为 `codex-cross-project-engineering-assistant-enhanced`。两个 Plugin 不重复分发 Skill。

这不是双规则产品：十个 Skill 继续来自同一规则源；伴随组件只承载 Hook 和运行时依赖。没有 Python、Profile、索引、台账或 Hook 时，安装者仍可通过基础 Plugin 开始普通工程任务。启用过 Operation v2、capability gate 或 Required 预算的安装者若失去增强运行时，对应受控操作必须停止，不能退回基础路径绕过控制。

## 固定基线

| 项目 | 已核验事实 |
| --- | --- |
| 公开稳定基线 | `v7.8.1` / `22d287fbd45e6f5a91d4ea9bf17e83f19f7d403f` |
| 当前候选分支 | `codex/plugin-ux-cost-v790` / `7ffd6a2e7792c257ba7c07a5ded9589bd1b65a76` |
| 接续的既有候选修改 | 分层契约文档（`68fb4e3`）和 `doctor --summary` 雏形（`7ffd6a2`） |
| 当前工作区 | 干净；未改写既有提交 |
| 原生安装接口 | 实机 CLI 帮助确认 `codex plugin marketplace add <SOURCE>` 与 `codex plugin add <PLUGIN@MARKETPLACE>` |

## 三类代表性任务与测量口径

| 任务 | 当前基线路径 | 已有可复现测量 | 仍需在 S5 实测 |
| --- | --- | --- | --- |
| 简单局部修改 | 主 Agent + 当前源码 BASIC；不应需要索引、台账或子 Agent | 静态规则/调用链已定位，尚无真实任务 Trace | 规则与 Reference 读取字符数、工具数、子 Agent 数、耗时 |
| 普通功能修复 | 定向验证，按风险决定独立复审 | `test_doctor_preserves_fields_and_adds_feature_checks_and_remediation`：0.089 s | 真实仓库修复的验证、复审与返修次数 |
| 高风险变更 | 完整安装事务、Hook/预算与独立复审 | 隔离 fake-Codex `install → verify → uninstall`：19.022 s | Windows/Ubuntu/macOS 真 CLI、实际 Hook 与严格预算阻断 |

19.022 秒使用测试夹具中的受控 fake Codex CLI，证明事务路径可重复，**不**证明真实账户首次成功时间或 Desktop 加载。当前未保留可归因于三类任务的历史 Trace，不能倒推规则字符数、工具调用、等待时间或成功率；S1 起按本表字段采集，并在 S5 用相同仓库快照冻结 25% 的正式门槛。

## 当前组件归属

| 组件 | V7.8.1 当前归属 | V7.9.0 目标归属 | 迁移/卸载不变量 |
| --- | --- | --- | --- |
| 十个 Skill 与入口元数据 | 主 Plugin payload | 基础 Plugin | 仅一份 Skill；基础可独立安装 |
| Hook、Python runtime、`cp-runtime.py`、`evolution.py` | 主 Plugin payload 和账户工具目录 | 增强伴随组件/增强安装事务 | 基础不启动；受控功能失效时 fail-closed |
| 全局受管 `AGENTS.md`、七个 Reviewer | 账户安装事务 | 增强安装事务 | 保留标记外内容、未知文件和备份 |
| capability gate、Operation v2、预算、偏好与任务状态 | 仓库外状态和增强运行时 | 保持原位置与所有者 | 旧状态迁移为 enhanced；不可被 base 删除或降权 |
| Marketplace、Plugin cache、安装 state 与事务日志 | `package_manager.py` | 复用现有事务/恢复机制 | 各组件具备独立 digest、受管目标、备份标签和卸载所有权 |

## 分层设计决策

1. 基础 Plugin 通过原生 Marketplace 安装，不调用本包 Python、不需要 API Key，也不写 Profile、索引、台账或 Hook。
2. 增强伴随组件不含 `skills/`，只在选择增强能力时登记。因此宿主不会发现同名 Skill 两次。
3. 增强安装继续复用 `package_manager.py` 的备份、journal、恢复、verify 和 drift 保护；不新建事务引擎。
4. 旧 V7.8.1 的完整安装在首次 V7.9.0 升级时归类为 `enhanced`。未知 state 字段、OFF 偏好、历史数据和备份必须原样保留。
5. 默认状态输出改为四项摘要：现在能做什么、受影响能力、原因、唯一下一步；`--json` 保持详细机器格式。现有 `doctor --summary` 雏形不满足“默认摘要”约束，必须连同兼容调用方测试一起调整。

## 回退与停止条件

升级前保持 V7.8.1 的完整备份；基础安装失败只清理本次由原生 CLI 新建的基础注册/缓存；增强失败由现有 journal 回滚。若发现已启用 gate、Operation v2 或 Required 预算能够通过基础路径执行本应受控的写入，立即停止 S1，恢复上一个稳定候选，且不发布 V7.9.0。

## S0 通过状态

基础原生命令契约、当前完整安装事务和不重复 Skill 的结构已经定位；正式基础 Marketplace 原型、旧版升级、增强卸载、真实 Hook 和跨平台验证尚未完成。因此 S0 的设计决定已冻结，实施门槛仍由 S1/S2 的隔离验证决定；在这些验证通过前不改写当前公开安装流程。
