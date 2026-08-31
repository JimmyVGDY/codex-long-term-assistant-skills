# CHANGELOG

English current-release summary: [CHANGELOG.en.md](CHANGELOG.en.md)

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
