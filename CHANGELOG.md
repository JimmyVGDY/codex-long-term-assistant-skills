# CHANGELOG

English current-release summary: [CHANGELOG.en.md](CHANGELOG.en.md)

## 未发布

暂无。

## 7.4.3 - 2026-09-04

### Changed

- 模型治理改为只使用派发前批准档位、permit 引用、预留单位与结果归因；宿主实际模型身份和推理强度不再被读取、推断、保存、证明或用于计费与发布门禁。
- TaskOutcomeEvent 升级为 V3、DelegationBudget 升级为 V2、Reviewer 结果升级为 V4；校准与 Evolution 改为比较批准档位的结果价值和单位成本。

### Fixed

- 旧 Event V2 与 Budget V1 链先按原始合同验证，再执行递归安全投影；新旧 schema 使用独立链并拒绝混写。
- Reviewer 旧状态迁移不再重新序列化历史运行时模型字段；发布脚本新增隐私边界和抽象派发策略门禁。
- 账户重装不再复制 Python 字节码，Hook、worker 与账户工具不再污染受管 Plugin cache；SessionEnd 签名队列的原子创建、扫描与移动支持 Windows 长路径；Windows Hook 统一为 CRLF，载荷摘要不再受 checkout 换行归一化影响。

### Validation

- 本地单元、双语、隐私、生命周期、兼容链、可复现构建、独立复审与 Windows 账户级重装证据在 V7.4.3 报告中分层记录；远程 CI、推送、标签和公开 Release 必须另行读回。

## 7.4.2 - 2026-09-04

### Changed

- 将闭合兼容注册表锚点推进到 Codex CLI 0.153.2，活动窗口更新为 0.153.2 至 0.148.0 的 11 个稳定发行版。
- 同步升级 Plugin 清单、安装器、双语构建、验证脚本、文档站和 Windows/Ubuntu 兼容矩阵；V7.4.1 历史证据保持不变。

### Fixed

- 固定 0.153.1/0.153.2 官方制品与规范化 CLI/Plugin 摘要，继续对未来版、预发布版和退出窗口版本失败关闭。
- 增加模型切换后不复用无可信证明的运行证据，以及 `unified_exec` 不消费子 Agent 派发许可或预算的回归。

### Validation

- 0.153.1/0.153.2 Windows 隔离 CLI、Plugin 往返、合成 Hook 与制品校验通过；全窗口、真实账户、CI、复审和公开发布证据在 V7.4.2 报告中分层记录。

## 7.4.1 - 2026-09-03

### Added

- 新增闭合 Codex 兼容注册表，按稳定发行版计数固定 0.153.0 与此前十个稳定版本，并绑定官方 npm 制品、能力 profile 和逐层证据状态。
- 新增 Windows/Ubuntu 22 单元发布矩阵、隔离 `CODEX_HOME` Plugin 预演，以及 schema 3 CLI/注册表/能力/payload 宿主快照。

### Changed

- Plugin 模式从单一 0.153.0 扩展到 11 个固定稳定版本；未来版、预发布版和窗口外版本仍失败关闭。
- Marketplace 合并改为最小字段所有权，保留未知顶层、嵌套 `interface`、`owner` 和其他 Plugin 条目。
- Hook snake_case/camelCase/兼容别名统一登记；安全字段冲突拒绝派发，观察字段冲突保持不可用，Stop 与 SubagentStop 返回中性 JSON。

### Fixed

- `verify/status/doctor` 不再只比较版本，而是检测 CLI 文件、注册表、profile 与能力摘要漂移并进入必须重装状态。
- Windows 兼容矩阵可显式绑定目标 Codex 可执行文件，避免 PATH 解析误用全局版本。
- 发行构建与运行文本审计排除仓库外 `project-context` 证据目录，防止临时官方 CLI 被误打包。

### Validation

- 11 个官方 Windows CLI 在注册表摘要 `1c204bd34cc355d5771376278c6251a5e133b7db09a7613b5c35d5c7bcdcbdd8` 下逐版通过 CLI、隔离 Plugin 与合成 Hook 单元；GitHub Ubuntu、真实账户和公开发布状态继续单独记录。

## 7.4.0 - 2026-09-03

### Added

- 新增仓库外 DelegationBudget V1 追加式哈希账本，统一管理 Reviewer、Explorer、Worker 的根任务加权单位、派发数、并行数、嵌套深度、角色上限和 Terra High 上限。
- 新增七个受控路由原因、显式 dispatch permit、幂等 reservation、可信实际档位补扣、宿主未启动证明释放和任务预算关闭合同。
- 新增三角色场景化收益样本与相邻档位离线回放；只有主协调 Agent 可最终化，所有优化建议保持 `execution_authorization=NONE`。

### Changed

- Task Envelope 升级到 schema 3、execution-state 升级到 schema 4；V7.3 字段自动映射到统一预算对象。
- review-state 升级到 schema 6；Reviewer 控制器只维护复审轮次、Finding 和统一预算引用，不再拥有总成本。
- Plugin 与本地 Marketplace 目标切换到 Codex CLI 0.153.0；安装清单生成必需的 `interface.displayName`。当前版加前十个稳定版的兼容窗口延后到 V7.4.1。

### Fixed

- PreToolUse 在账本启用时对缺少稳定派发 ID、未知角色、permit 不匹配、预算耗尽和损坏链失败关闭；重复 Hook 不重复扣费。
- SubagentStart/Stop 缺少 reservation 关联时不再按时间或顺序猜测；状态保持未关联，普通 Hook 模型字段不会冒充可信实际模型证据。
- 启动后的完成、失败或取消均不退款；只有宿主明确证明未启动时才释放预占。

### Validation

- 新增统一预算、并发竞态、嵌套根预算、Hook permit、Reviewer 单一计费、隐私、哈希篡改、父级校准和不足样本不调整回归。完整包、账户级 0.153.0 安装、独立复审与公开产物证据在发行报告中分别记录。

## 7.3.0 - 2026-09-02

### Added

- Reviewer 派发新增 `minimum_acceptable_profile`，并增加追加式 `INLINE/DELEGATE` 决策门；`INLINE` 不创建轮次或消耗 Reviewer 预算。
- Reviewer v3 结果模板新增任务难度、耗时、待最终化归因、finding 处置和 `profile-weight-v1` 估算成本，并由控制器投影到去重校准台账；Reviewer 不能自行最终化归因。

### Changed

- Reviewer 自报只可形成 `declared_match/fallback_acceptable/underpowered/unverified/mismatch`；低于最低可接受档位的结果只能记为 `incomplete`，且不能正常归并或关闭。
- Evolution 将缺失成本保持为 unknown，按 Reviewer、模型档位和任务难度统计，并排除未最终归因的数据参与低收益判断；真实样本不足时保持默认路由不变。
- 双语文档站把 V7.3 当前系统架构、领域路由、配置、受控演进和事实源注册表统一为现行口径；旧版本只保留为迁移或历史证据。
- 历史详情页在生成阶段增加中英文醒目标记并退出默认站内搜索，当前索引与历版发行索引继续可检索。

### Fixed

- 修复 Plugin 模式启动器被历史 standalone runtime 抢先命中、从而加载旧策略契约的问题；Plugin 模式现在只使用安装状态绑定的版本化缓存，缓存缺失时失败关闭。
- 移除当前导航和现行规范中的历史版本混排，修复指向已移除校验器的失效命令。
- 统一此前内容分叉的中英文 Codex 配置指南，并增加当前文档清单、历史隔离和公开脚本存在性回归门禁。
- 修正英文现行页的中文入口自指、中文标题锚点和遗留表头，并让版本变更触发 Pages 及站点入口一致性失败关闭检查。

### Validation

- 新增最低档位、INLINE 改判、旧 v2 结果兼容、校准投影、未知成本及未完成归因回归；本地安装与真实数据读回结果在本任务交付时单独记录。

## 7.2.0 - 2026-09-02

### Added

- 新增 11 个真实 Codex 宿主路由验收场景、schema 2 观察格式和 SHA-256 绑定的最终报告证据。
- 新增受控演进从 observation、snapshot、assessment 到 `execution_authorization=NONE` proposal registry 的持久化端到端用例。

### Changed

- Python 最低版本固定为 3.11，Windows 与 Ubuntu CI 同时覆盖 3.11 和 3.13。
- 受控演进按信号分别判定证据充分性，并按唯一 `task_id` 计算覆盖率；模型升级和负面结果只读取各自必要证据。
- `long-running-task-memory` 与 `multi-agent-independent-review` 移除重复受控演进正文，统一引用 `controlled-evolution-governance`。

### Fixed

- 完整验证现在绑定 Git index、受管与未跟踪内容摘要、删除与链接状态，即使被中断也执行后置快照；验证输出拒绝写入仓库。
- 宿主路由验收拒绝未知 Skill、重复任务或报告、非有限通过率、哈希/字节数不一致及报告字段漂移，并明确区分宿主最终报告与内部路由 Trace。
- 安装器移除 Codex CLI 0.152.1 不接受的本地 Marketplace 顶层 `owner/interface` 字段，同时保留未知外部元数据。

## 7.1.0 - 2026-09-02

### Changed

- 当前 Codex CLI 发行基线升级到 0.152.1；安装器保留 0.150.1 已验证兼容，对其他版本继续失败关闭。
- Manifest、Plugin、双语构建、发行验证、证明、文档站与当前操作指南统一升级到 7.1.0，并加入 7.0.0 升级路径。

### Fixed

- Plugin 模式现在事务化安装并校验账户级 `cp-runtime.py` 与 `evolution.py`；两个启动器在账户 runtime 不可读时，会按安装状态精确回退到当前版本 Plugin cache，避免受限任务误报 `cp_runtime` 模块缺失。
- 在 Windows 原生 Codex CLI 0.152.1 上保留 Marketplace/Plugin 命令和 `plugin list --json` 核心契约校验。
- 将完整包验证的单命令超时从 300 秒提高到 600 秒，避免 GitHub Windows Runner 在测试通过前被固定时限中断。

## 7.0.0 - 2026-09-01

### Added

- 新增语言中立的 `backend-engineering`，覆盖 Node.js、Go、.NET、Rust、Java、Python 与混合语言服务端工程。
- 新增独立的 `ai-engineering`，覆盖模型接入、结构化输出、RAG、Agent、评测、推理、GPU 与多模态语义。
- 新增四主领域职责矩阵及 45 条正反路由用例。
- 将文档站根页重构为双语项目入口，增加项目定位、语言卡片、能力指标、发行与源码入口，并补充响应式、深浅色和键盘访问适配。
- 增加全仓库 Markdown 路径、锚点和同仓库 URL 检查，并通过定时工作流补充外部链接探测。
- 增加由 GitHub Actions 发布的中英文独立文档站，提供导航、搜索、主题切换和版本化发行资料入口。
- 增加标签版本失败关闭、双语可复现产物、GitHub 签名来源证明和仅创建草稿的 Release 自动化。
- 为 V1.0.0 至 V6.6.0 增加双语 GitHub Release 页面索引，并明确历史原始 ZIP 不公开上传的零附件策略。

### Changed

- Java 与 Python 从顶层 Skill 调整为通用后端的渐进专项；数据域更名为 `data-middleware-infrastructure` 并移出 AI 产品语义。
- Manifest、AGENTS、中英文文档、安装恢复、发行脚本和包验证统一升级到 7.0.0。
- 双语文档站首页、导航与安全支持范围切换到 V7；项目预览图移除具体版本号，并改为 GitHub 推荐的 1280×640、低于 1 MB 的可复用 JPEG。
- 主 CI 从受约束发布元数据读取版本、包名和见证文件名，不再硬编码旧版本。

### Fixed

- 修复 Material for MkDocs 将仓库版本信息缓存在浏览器会话中，导致页眉沿用 `v6.6.1`；站点现在同步修正缓存与当前页面中的版本事实。
- 升级安装仅清理 Manifest 声明的四个旧 Skill 目录（三个 V7 领域替代项及此前废弃的 Vue Skill），保留未知 Skill 与自定义文件。
- 工作区链接审计忽略已从工作树删除但尚未写入 Git 索引的旧路径，支持重命名中的一致验证。
- 修复文档站语言入口模板在仓库检查与 Pages 生成目录之间的路径差异。
- 修复新增同级英文文档未进入 Pages 英文源目录导致的严格构建失败。

### Validation

- 45 条路由用例、128 项 package 测试、6 项 runtime 测试、双语严格审计、Markdown 链接审计和 MkDocs 严格构建通过。
- 源码树在 Windows Codex CLI 0.150.1 完成 `6.6.0 -> 7.0.0` Plugin 升级读回，并由全新只读任务命中通用后端与数据基础设施路由；公开 ZIP 仍由标签工作流独立构建和证明。

## 6.6.1 - 2026-08-31

### Added

- 增加 `zh-CN` 与 `en` 两个完整、可独立安装的确定性发行包。
- 增加全部自然语言文档、10 个 Skill 及其 Reference/模板、7 个 Reviewer、示例、结构化说明和 Python 运行时提示的人工英文配套。
- 增加双语发行结构、locale 绑定、可复现构建、全项目翻译覆盖审计和运行时字面量失败关闭门禁。

### Fixed

- Windows 原子文件发布遇到短暂共享冲突时实施有界重试。
- 延迟封印生命周期测试显式等待验证进程退出，消除临时目录回收竞态；生产 SessionEnd 仍保持预算外异步封印。
- Windows 批处理启动器固定使用 UTF-8 代码页与 CRLF 行尾；中性语言门禁区分不随包发布的运行时源字符串目录和实际对外文案。

### Security

- 保持 `execution_authorization=NONE`、项目双重隔离、最小元数据记录和 Terra High 自动上限。
- Reviewer TOML 不写死模型；诊断模型观察不冒充实际运行模型证明。
- 两个发行包均排除无关品牌、个人路径、嵌套 ZIP、Git 元数据、缓存和语言覆盖层源码。

## 6.4.0 - 2026-08-28

### Added

- 规范化 Plugin payload manifest，以及 ZIP、Marketplace、cache 三段同源 digest 验证。
- 事件安全分段、跨段连续读取、半记录审计隔离和真实进程崩溃恢复。
- Codex 0.150.1 Plugin/Marketplace 命令能力探测与统一发行验证器。
- state schema 1 到 2 的显式迁移、未知字段保留和未知 schema 失败关闭。

### Changed

- Marketplace 从整树目标改为本包 payload 子树与 manifest 条目级合并。
- Plugin cache 纳入事务 journal、备份、恢复、digest 和激活后读回。
- 宿主实际模型、推理强度和终态只接受明确字段，不再从通用别名推断。
- 事件链读取增加严格 schema 校验；显式非法终态和未知实际模型失败关闭。

### Security

- 摘要、备份、复制和删除前递归拒绝受管树内部符号链接、Junction 与 Reparse Point。
- 保持 `execution_authorization=NONE`、人工 Proposal 决策、项目双重隔离和自动 Terra High 上限。
- 保留未知账户资产、历史项目上下文、自观察数据和升级备份。

## 6.3.0 - 2026-08-28

### Added

- 持久化安装/卸载事务、互斥锁、状态读取与崩溃恢复命令。
- 同一真实 Codex 会话的五类生命周期事件验收与隐私安全摘要。
- 生命周期完整率、SessionEnd 覆盖率和缺失/重复/乱序/串线告警。
- Reviewer 发现归因、采纳、修复、重复、回归预防、时长和成本代理指标。
- 字节级确定性 ZIP 构建、双构建见证和机器可读发行证明。

### Changed

- 安装与卸载在首次受管写入前记录旧状态、备份、文件动作和 Plugin 注册动作。
- 自观察在证据或因果链不足时输出 `insufficient-evidence`，不从发现数量推断收益。
- Codex 0.150.1 与 Plugin CLI 能力在写入前验证，不兼容时失败关闭。
- 发布校验入口、Manifest、Plugin 元数据和文档统一到 V6.3.0。

### Security

- 恢复与回滚继续拒绝 Junction、Reparse Point、符号链接、未知内容和归属漂移。
- 发行证明只保留白名单摘要与证据哈希；原始会话与任务标识以 SHA-256 引用代替。
- 保持 `execution_authorization=NONE`、人工 Proposal 决策、项目双重隔离和自动 Terra High 上限。

## 6.2.0 - 2026-08-28

### Changed

- 将 V6.1 Windows 原生 Codex CLI 0.150.1 实机修复正式纳入发行包，不再依赖安装后本地补丁。
- 六个 Windows Hook 统一通过 quote-free `cmd.exe /d /c %PLUGIN_ROOT%\hooks\cp_hook.cmd <HookName>` 启动。
- Windows Hook 启动器优先解析本机账户 CPython，再回退 `python.exe` 或 `py.exe -3`，无需创建 `python3.exe`。
- Hook stdin/stdout 固定为 UTF-8，并兼容 Codex 0.150.1 中文 Stop payload 截断；Stop 始终返回合法中性 JSON。
- 安装器 staging 名称缩短，并在受管文件 I/O 边界使用 Windows extended-length path，覆盖长路径备份、复制、验证、卸载和回滚；Windows 测试夹具使用 `USERPROFILE`、fake `codex.cmd`、超长目录和 Junction。
- 卸载按标记合并恢复 `AGENTS.md` 与 standalone `hooks.json`，不再整文件覆盖安装期间新增的外部规则或自定义 Hook。
- 自动子 Agent 显式模型改为精确 Luna/Terra allowlist；未知或未来 Terra 名称按 fail-closed 拒绝。
- 全部自然语言说明、规则、Reviewer 提示和测试身份改为中性表达；机器契约中的 `--scope user`、字段名和路径变量保持兼容。

### Validation

- 增加 Windows Hook launcher、UTF-8/截断 Stop 和 Terra High 上限回归测试。
- V6.2 发布包通过语义校验、35 条路由用例、27 个单元/回归测试，以及 Codex 0.150.1 隔离 V6.1→V6.2 Plugin 升级/恢复闭环。
- 语义校验新增中性语言门禁，阻止具体姓名、第一或第二人称及对话化措辞重新进入发行包。

### Security

- 保持 `execution_authorization=NONE`、人工 Proposal 决策、项目双重隔离和自动子 Agent 最高 Terra High。
- 不自动修改 Skill、Reviewer、主 Agent 模型、业务仓库，不自动提交、推送、部署或操作生产环境。

## 6.1.0 - 2026-08-27

- 修复 Codex CLI 0.150.1 Marketplace/Plugin 实际注册与 installed/enabled 读回。
- 增加 Unix/Windows Hook 双入口、SessionEnd 3 秒 timeout 和 WSL 风格 CODEX_HOME 转换。
- 保留 10 Skills、7 Reviewers、TaskOutcomeEvent V2、受控演进和 Terra High 自动上限。

## 6.0.0 — 插件化确定性自观察版

- Plugin-first + standalone/repo 双兼容安装。
- 账户 Skill 目录修正为 `$HOME/.agents/skills`。
- 六类 Hooks + TaskOutcomeEvent V2 + Task 聚合。
- `project_id + repo_fingerprint` 双隔离。
- Terra High 自动上限与 PreToolUse 前置拦截。
- 不可覆盖 Snapshot、source_digest、Proposal 完整生命周期。
- 安装事务统一、安全备份、漂移检测、符号链接/Junction 防护。
- 新增 `controlled-evolution-governance`，总 Skill 数 10。

## 5.1.0 - 2026-08-26

### Added

- `runtime/cp_runtime/evolution` 受控自进化权威实现；
- Self Observation、Value/Complexity Analysis、Optimization Proposal 和 Human Decision 链路；
- Proposal/Decision 追加式哈希链、去重、人工 ACCEPT/REJECT/DEFER 与完整性验证；
- 数据源路径隔离、JSONL 失败关闭、敏感字段脱敏和 Reviewer 退役高置信度门槛；
- `scripts/evolution.py`、PowerShell/CMD 包装器、V5.1 专项测试与操作文档。

### Changed

- 全局路由新增受控自进化触发边界：普通任务只记录 Feedback，不自动运行完整分析；
- 包版本、README、Manifest、语义校验和发布校验统一到 V5.1；
- 接受提案仍需另建实施任务，重新经过 Task Envelope、Approval、Execution Guard、独立 Review 和 Finalization。

### Security

- 所有提案的 `execution_authorization` 固定为 `NONE`；
- CLI 不提供 `execute`、`apply`、`autofix`、`self-modify` 或 `auto-accept`；
- 项目串线、数据源越界、哈希链损坏、记录格式错误或证据不足时失败关闭。

### Compatibility

- 保留 V5.0 的 9 个 Skill、7 个 Reviewer、项目治理、Approval/Evidence、Checkpoint/Memory、Finalization 与安装恢复流程；
- V5.0 项目上下文可直接复用，新增 Evolution 数据仍位于业务仓库外。

## 5.0.0 - 2026-08-26

### Added

- Project Profile、Project State 与已有项目有界只读 Onboarding；
- Task Envelope V2 六维路由：复杂度、项目阶段、执行档位、Reviewer 预算、模型档位与宿主表面；
- Approval、Evidence、Finalization 三类独立合同及项目/任务/环境/仓库基线绑定；
- Task Checkpoint → Project Memory Projection → Knowledge Candidate 受控晋升链路；
- 共享 `runtime/cp_runtime` 与安装后 `tools/cp-runtime.py` 入口；
- 项目治理、执行守卫 V5 集成和安装恢复安全回归测试。

### Changed

- `execution_guard.py` 升级为 schema 3，并兼容读取旧任务状态；
- 安装器增加运行时与工具安装、源码目录保护、符号链接防护和备份完整性校验；
- 强制重建 Project Profile 时保留已存在的 `project-memory.md`，防止长期记忆被静默覆盖；
- Approval、Evidence、Finalization 与记忆候选默认必须写在业务仓库外，避免治理文件反向改变仓库指纹；
- 当前文档、语义校验和发布验证统一到 V5.0。

### Security

- Approval 仅允许受保护操作，禁止过期授权在签发时进入 Active；
- Project Profile 绑定时检查仓库路径、Project ID、完整性及 Remote 变化；
- Finalization 校验 execution-state 与实际仓库一致，并阻断无读回证据的外部动作声明。

### Compatibility

- 保留原有 9 个 Skill、7 个 Reviewer、Luna/Terra 四级路由和 Reviewer 成本预算；
- 不自动改写现有 `config.toml`，不自动删除 `project-context/`；
- V4.2 的 Review Packet、Review Controller、Checkpoint 和原 `execution_guard` 命令保持兼容。

## 4.2.0 - 2026-08-12

### Added

- Luna Low、Luna Medium、Terra Medium、Terra High 四级自动子 Agent 模型路由；
- Reviewer 请求模型、运行时模型和策略状态审计；
- 审查包摘要、差异统计、文件状态和 freshness 检查；
- 相同 Reviewer/相同 packet、零发现重复轮次和 Terra High 升级理由保护；
- 检查点内容指纹与重复 append 自动跳过；
- Codex `config.toml` 分步配置指南、模型成本策略和 V4.2 设计文档；
- Reviewer 与检查点新增回归测试。

### Changed

- 默认复审预算从并行 6/累计 12/三轮收敛为并行 3/累计 6/两轮，保留显式兼容硬上限；
- 7 个 Reviewer 改为渐进读取、唯一职责、根因合并和结构化最小输出；
- 所有 Skill 增加模型与委派成本规则，辅助工作优先 Luna；
- 长期记忆从连续 5 个实质动作改为 8 个，恢复窗口从 5 个检查点降为 3 个，热区从 30 降为 20；
- 全局 `AGENTS.md` 压缩为跨项目核心规则，减少与 Skill Reference 重复。

### Compatibility

- 主 Agent 模型不被安装包改写；
- Reviewer TOML 不固定模型，动态派发仍可按风险升级；
- V4.1 高预算仍作为控制器硬上限存在，但普通流程不会自动启用。

## 4.1.0 - 2026-07-31

### Added

- LIGHT/STANDARD/STRICT 执行档位与阶段状态机；
- 任务执行信封、证据指纹和自动失效；
- Reviewer 统一审查包、结构化结果 Schema 和成本档位；
- 子 Agent 独立上下文委派协议；
- dry-run、doctor、备份 manifest 和一键恢复；
- 语义一致性校验；
- Codex 账户 Skill 路径自适应与旧路径重复检测；

### Changed

- Java、Python、数据、质量、可观测性、长期记忆、多 Agent 复审和技术文档的大 Reference 改为按需分片；
- 质量 Skill 不再默认对所有改动机械执行完整多 Agent 复审；
- Reviewer 使用独立上下文，只接收最小审查包并返回结构化摘要；
- 修复 review_controller 中“父会话声明只读但写入探针成功”仍可能判为系统只读的问题；
- 清理过时 Vue/v3.2 语义和脚本相对路径。
# V6.5.0

- 增加诊断级宿主事实适配器，不允许 host-only 模型证据进入发行通过状态。
- 增加主机绑定 keyring、独立用途轮换和 detached event seal。
- 增加 Reviewer 稳定结果身份、重放去重、冲突检测、Wilson 区间和校准状态。
- 保持 TaskOutcomeEvent 2.0、Plugin/Marketplace 身份、Terra High 上限和受控演进授权边界。

# V6.6.0

- 增加可信宿主模型证明契约，并固定请求策略、运行时证据和诊断旁证三个独立字段。
- 共享状态锁改用进程所有的原生文件锁，增加 spawn 多进程、强制终止和 keyring 原子替换故障测试。
- SessionEnd 改为签名入列与 detached worker 延迟封印，不执行全链扫描。
- Reviewer 校准增加任务难度、根因簇重复、采纳原因和回归预防证据率。
- 增加非破坏事件归档、容量预算和隐私受限的跨项目健康概览。
- 保持 TaskOutcomeEvent 2.0、历史 key、项目双重隔离、Terra High 上限和 `execution_authorization=NONE`。
