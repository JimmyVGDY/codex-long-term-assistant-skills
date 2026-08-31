# CHANGELOG

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
