# CHANGELOG

English current-release summary: [CHANGELOG.en.md](CHANGELOG.en.md)

## 7.8.0 - 2026-09-10

- 新增 C01-C25 `capability-registry/1`、AUTO/BASIC/ASSISTED/FULL 功能级选择和仓库外显式偏好；档位、风险与外部权限保持独立。
- 新增 `onboarding/1` 与可恢复扫描任务：一次询问、nonce/revision CAS、续期、取消 epoch、租约 fencing、游标与部分覆盖读回。
- 新增范围复审依赖指纹；未知动态依赖为 `INCOMPLETE`，相关变化为 `STALE`，全仓发行审计保持独立。
- 安装器增加 Python 3.11+ 真实预检、分功能 doctor、只读 inventory、无 state 零删除预览、非 Git BASIC 指南及惰性偏好迁移。
- U02-U13、UX01-UX40、M01-M12 与 T25-T28 建立逐项合同和可发现测试；V7.6.2 消息边界与 V7.7.0 Operation v2 保持回归覆盖。

## 7.7.1 - 2026-09-10

- 将闭合兼容注册表推进到 OpenAI Codex CLI 0.154.0，活动窗口固定为 `0.154.0`、`0.153.4`、`0.153.3`、`0.153.2`、`0.153.1`、`0.153.0`、`0.152.1`、`0.152.0`、`0.151.0`、`0.150.1`、`0.150.0`，并将 0.149.1 移出活动窗口。
- 固定 0.154.0 的官方 Git tag/commit、Hook discovery、PreToolUse/PostToolUse schema、成功 `apply_patch` 结果源码、npm SRI 与 SHA-256；新增只绑定 0.154.0 的 `result-v154` profile。
- 修复已配置但停用的能力门禁在不存在在途 Operation 时错误阻断 PostToolUse；停用后的既有在途 B 仍按原合同收敛。
- Windows CLI、账户 Plugin 7.7.1、三方 payload 摘要与真实新任务均已读回通过；完整证据保留在 V7.7.1 发行记录。

## 7.7.0 - 2026-09-10

- 新增仓库外 Operation v2 写前协议：首次 `apply_patch` A 只创建起点并拒绝，准备后由不同 B 原子领取 READY，真实 PostToolUse 回执后才允许完成验证。
- `capability-task-prepare/finish/check/cancel` 新增 `--operation-ref` 路径；CLI 不创建宿主起点或 dispatch ID，旧 GateTask schema 1 保持隔离兼容。
- 补齐 Add/Delete/Update/Move、多目标、UTF-8/路径/文件预算、并发领取、取消、过期、策略变化、缺失/错误回执、范围证据与索引维护回归。
- 兼容注册表为 11 个冻结 Codex 版本新增官方 PreToolUse/PostToolUse schema 的 tag、commit、路径和 SHA-256；安装器只在该能力为 SUPPORTED 时注册强制 Hook。

## 7.6.2 - 2026-09-09

- 修复 UserPromptSubmit 的异步 Hook 注册，并将对应宿主能力证据纳入兼容性合同；不再把可选反馈流程作为普通提示的前置阻断。
- 隔离旧版能力门禁状态：启用旧策略时原生写入安全失败关闭，未配置或已停用策略保持中性；Stop/UserPrompt 不再读取或改写旧任务状态。
- 定向验证覆盖 Hook 注册、旧门禁隔离、失败关闭和状态不变性；完整发行验证、独立复审、提交、推送、发布、安装与生效状态另行记录。

## 7.6.1 - 2026-09-09

- 修正 Hook、迁移边界、预算 Owner 和格式描述；统一英文来源与事实检查。
- 建立稳定文档入口并保留旧路径/锚点；按清单归档历史产物。
- 发行源码采用 Git 受管集合或显式哈希快照，拒绝缺失、篡改、路径冲突及链接；双语覆盖仅使用捕获来源。
- 验证状态详见 V7.6.1 验收记录；旧版本结果不替代最终候选验收。

## 7.6.0 - 2026-09-09

- Windows CI 发现短路径别名与规范路径混用：ReadBudget 复用既有拒绝链接的 safe_path 统一根身份，安装入口测试比较规范路径，并增加真实 Windows 短路径回归；项目隔离和读取/超时预算保持。

- 自然验收发现临时决策JSON会意外进入项目修改范围：宿主提示、CLI帮助及双语流程明确其仓库外任务目录位置，保留原范围检查，不将临时文件豁免或事后追认为已准备修改。

- 根据自然任务验收收紧冷索引免初扫例外：按累积范围只允许单个既有文件，跨文件范围升级须在修改前扫描，旧不合格无索引PASS在核验时失效；保留简单单文件修复和原读取预算。

- 经项目显式启用的可选流程门禁加入真实宿主起点、写前准备、索引维护回执、Stop当前证据检查与有限补救，以及Interrupt取消；未启用项目保持旧行为。新增双语操作说明，修复外部状态的Windows长路径及UNC转换。流程PASS与业务语义、包验证、账户安装和新任务验收分别报告，不扩大原授权与委派预算。

- 独立复审后修复同定位符公开声明类别未更新的问题，保留显式服务/适配职责及人工说明；结束维护纳入已核实并实际采用的过期候选，即使其源码未改动。已绑定项目先查询确认索引状态，避免未确认就进入无索引分支；自然任务的流程遗漏仍单独诊断和验收，不以包测试替代。
- 修复变更后重复扫描额外写版本的问题，分离物理新鲜度与旧语义核验；统一登记和恢复的重复JSON字段拒绝。查询缺失与失效结果提供有范围的后续维护提示，前后端直接连接质量入口；相关回归与独立新任务验收分别记录。
- 能力索引入口明确已有索引的小改动仍需查询、首次共享接口变更需限定初扫及协调者结束核对；拒绝把工作区索引容器当作独立快照目录，防止意外创建并行索引。
- 新增可选项目能力索引：工作区身份绑定、有界扫描、查询前核实、显式失效/迁移/弃用、精确revision更新与快照恢复；保存每条能力的观察基线与时间，复用现有锁和完整性工具。原项目接管与稳定记忆默认流程保持；已接入开发Skill的查询、维护成本判断与变更后更新；候选行为及安装验收已完成，成本收益尚未证实。默认扫描跳过.agents/.codex工具目录，显式源文件范围仍可识别。契约见[能力索引](docs/CAPABILITY_INDEX.md)。
- 新增组件与模块复用公共规则，接入前后端修改前流程与共享实现验证；优先查找已有能力，保留有依据的独立实现和旧使用方兼容。
- 补充功能、兼容和测试交付 Reviewer 的复用检查，以及现有审查包的决策摘要规则；不增加运行时 Schema 必填字段，规则阶段保持 Hook 不变；后续可选门禁仅扩展显式启用项目的流程检查，授权和预算协议保持。
- 增加 8 个隔离场景、隐藏行为断言和回放工具；区分静态可加载、行为通过和语义复审。方法与限制见 [复用验收规程](docs/COMPONENT_REUSE_ACCEPTANCE.md)。实测结果不代表所有项目的稳定性保证。


验收结果与限制见 [V7.6.0 验证报告](docs/releases/v7.6.0/VALIDATION_REPORT.md)。

## 7.5.1 - 2026-09-06

- 修正并发验收的时序假设：2 秒有界锁等待超时后，在其他调用结束后重试，并核验只提交一份事务；新增强制锁竞争、水位不推进及 worker 重试幂等回归。锁等待上限和运行时水位协议保持原合同。

## 7.5.0 - 2026-09-06

- Windows CI 发现短路径别名（例如 RUNNER~1）与完整路径混用会使相对引用失败。已用受限目录下的固定相对引用修复反馈枚举和回归跟踪，并从已核验 Profile 路径取得规范项目名；真实 Windows 短路径回归已执行通过。修复后定向回归与安装读回单独执行，首轮完整包结果属于修复前候选；最终全量结果以该修复提交的 CI 为准。

- 修复 Profile 与 Hook 指纹算法差异，统一默认和显式策略。
- 增加任务绑定、结构化验证证据与主协调者最终化反馈；Stop 自动关联报告，保留原始宿主终态。
- 分析前检查身份、策略、封印、覆盖和新鲜度；显式启用后按有效增量与冷却触发，支持幂等恢复。
- 新提案固定可检验假设；分别验证实施通过与观察收益，重放时复验引用，覆盖取消、回滚和终态。
- 校准按样本所属账本验证，同项目、同仓库、同场景按独立任务比较并保留不确定性。
- 已确认根因生成待审回归候选与后续复发率观察，保持 execution_authorization=NONE。

兼容窗口沿用已冻结的 Codex CLI 0.153.4 及此前十个稳定发行版。本次不宣称扩大宿主支持范围。自动化默认关闭，旧事件与提案哈希保持不变；缺少有效身份的分析入口现在返回阻断状态。

验证和交付事实见 [验证报告](docs/releases/v7.5.0/VALIDATION_REPORT.md) 与 [审计报告](docs/releases/v7.5.0/AUDIT_REPORT.md)。
## 7.4.6 - 2026-09-05

### Changed

- 将闭合兼容注册表推进到 Codex CLI 0.153.4，活动窗口继续保留 11 个稳定发行版并移出 0.149.0；固定官方 npm 制品、SRI、SHA-256 与规范化 CLI/Plugin 摘要。
- 同步更新账户安装器、兼容矩阵、发布验证、双语文档和站点索引。0.153.4 修复内置模型选择器中的 Astra 可见性并在未显式选模时将其作为内置默认，同时把异步提问说明限定为宿主提供对应工具时适用；Plugin、Marketplace 与 Hook 合同保持不变，自动子 Agent 仍只允许 Luna/Terra 档位。
- 补强语义发布门禁，强制保留从上一稳定包 V7.4.5 升级到 V7.4.6 的声明，并增加回归断言。

### Validation

- Windows 原生 CLI 通过同一 npm 全局通道从 0.153.3 更新到 0.153.4；0.153.4 官方制品与隔离兼容单元通过，V7.4.6 账户级事务安装、Plugin 激活、`HOST_COMPATIBLE` 和 182 文件三方 payload 摘要读回通过。
- 实际卸载/回滚与父子 Agent 生命周期旅程未执行；完整 11 版本矩阵、远端 CI、标签、六项资产来源证明和公开 Release 需在交付阶段独立读回。

## 7.4.5 - 2026-09-05

### Changed

- 将闭合兼容注册表推进到 Codex CLI 0.153.3，活动窗口保留 11 个稳定发行版并移出 0.148.0；固定官方 npm 制品、SRI、SHA-256 与规范化 CLI/Plugin 摘要。
- 同步更新安装器、兼容矩阵、发布验证、双语文档和站点索引。0.153.3 的 Amazon Bedrock/Astra 上游变化不修改 Plugin/Hook 合同，也不扩大自动子 Agent 的 Luna/Terra 路由策略。

### Validation

- Windows 原生 CLI 通过同一 npm 全局通道从 0.153.2 更新到 0.153.3；0.153.3 隔离兼容单元与 V7.4.5 账户级事务安装、Plugin 激活、`HOST_COMPATIBLE` 和三方 payload 摘要读回通过。
- 实际卸载/回滚与父子 Agent 生命周期旅程未执行；远端 CI、标签、资产来源证明和公开 Release 需在交付后独立读回。

## 7.4.4 - 2026-09-04

### Added

- 新增版本化 GitHub Release 标题：中文来自 `manifest.json.release_name`，英文来自 `locales/en/manifest-localization.json.release_name`；标题约束失败关闭，工作流通过 job output 与环境变量传递标题。
- 新增 Draft-only、既有 Release 不覆盖、双语资产/provenance 说明，以及历史标题回填的独立线上元数据边界。

### Validation

- V7.4.4 本地 package-only 验证与逻辑只读复审通过；远端 CI、标签、Draft 与公开 Release 保持待读回。v7.3.0 至 v7.4.3 历史标题回填已完成并逐个线上读回，v7.2.0 及更早未改；Codex CLI 0.153.2 兼容边界不变。

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
