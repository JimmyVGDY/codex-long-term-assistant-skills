# CHANGELOG

## 4.0.0 - 2026-07-31

### 通用前端工程增强

- `vue-frontend-engineering` 直接改名为 `frontend-engineering`，不保留兼容别名；
- 覆盖 Vue/Nuxt、React/Next/Remix、Preact、Angular、Svelte/SvelteKit、Astro/Solid/Qwik/Ember/Web Components、Alpine/HTMX、Ionic/Capacitor、传统页面与静态 HTML/JSP；
- 明确 Browser、SSR/Edge、PWA、WebView、Extension、Electron/Tauri Renderer 与主进程/原生桥边界；
- 新增安全运行时、质量性能、设计系统/SEO、微前端 Monorepo 等按需规则；
- 技术栈检测器升级为只读有界扫描，支持 Workspace、源码签名、无 package.json、Fullstack Web、Hybrid Web 和纯 Node.js 后端排除；
- 检测器自测扩充为 12 个，新增 Preact、Ionic/Capacitor、JSP、静态 HTML、Workspace、无效 package.json 和 Electron 负向场景；
- 新增并强化技术栈快照、前端审查报告和验证矩阵模板；
- 路由回归新增静态站点、JSP、Preact、Hybrid Web、Monorepo 和桌面主进程排除场景；
- 升级脚本备份并清理旧 Skill，验证脚本阻止旧名称和 Python 缓存文件残留；
- 更新全局调度、Manifest、示例、触发矩阵和文档；
- 继承 v3.3 Reviewer 运行时隔离修正。

# 变更记录

## 3.3.0 - 2026-07-29

### Reviewer 运行时隔离修正

- 根据 Windows Codex 运行时探针修正安全表述：在父会话为 `danger-full-access` 时，指定 Reviewer 即使 TOML 声明 `sandbox_mode = "read-only"`，仍可成功写入临时探针文件；
- 不再把 TOML `read-only` 声明或“本次没有写文件”表述为系统级只读隔离通过；
- 新增 Level A `system-readonly`、Level B `logical-readonly`、Level C `self-review` 和 `unknown` 四种隔离等级；
- 生产、真实数据、权限安全、不可逆迁移和用户明确要求严格只读的任务，要求整体只读父会话或有效系统隔离证据；
- 更新 7 个 Reviewer 的职责说明：保留 `sandbox_mode = "read-only"` 作为期望配置，但明确父会话可写时只能报告逻辑只读；
- 增加 `REVIEW_ISOLATION_EVIDENCE.template.md`，记录实际 Agent、TOML 路径、父会话沙箱、探针结果和严格只读资格。

### 复审状态控制器

- `review_controller.py` schema 升级到 v2；
- 新增 `isolation` 命令，持久化父会话权限、配置声明、探针结果、Agent 确认和证据摘要；
- `init` 新增 `--risk-level` 与 `--strict-readonly-required`；
- 严格只读要求未满足时，控制器阻止计划和派发 Reviewer；
- `status`、`validate`、`dispatch`、`result`、`merge` 和 `close` 均记录或校验隔离等级；
- 最终结论区分系统隔离复审、逻辑只读复审、未验证和失败，不允许逻辑只读冒充系统隔离。

### 安装与验证

- 用户级验证脚本改为只验证 Reviewer TOML 的配置声明，并明确提示运行时隔离需要单独验收；
- 包验证脚本新增逻辑只读、严格门禁和系统只读两条控制器路径测试；
- 新增 `docs/REVIEWER_RUNTIME_ISOLATION.md`，给出临时仓库受控探针、判断标准和双会话推荐流程；
- 升级版本为 `3.3.0`，保留 9 个 Skills 和 7 个 Reviewer 名称，支持从 v3.2 原地升级。

## 3.2.0 - 2026-07-29

### Skill 调度

- 增加一个主领域 Skill、默认两个辅助 Skill、无说明最多四个活动 Skill 的最小充分加载规则；
- 增加按分析、方案、实施、复审、文档和长期恢复阶段延迟激活工作流；
- 新增 16 条路由回归用例和 `routing-eval.py` 观察评分工具。

### 复审门禁

- 高风险任务增加实施前设计与影响审查，默认最多 1 轮、2～4 个 Reviewer；
- 实施前审查与实施后独立复审分离，不能互相替代；
- 新增实施前审查模板；
- 新增 `review_controller.py`，持久化并限制 pre/post 轮次、深度、并行数、累计 Reviewer 和修复轮次。

### 可观测性

- 日志 Skill 扩展 Logs、Metrics、Trace、Profiling、告警和发布/配置变更事件；
- 新增 Metrics、Trace 和多证据源关联模板；
- 明确在线 Profiling、扩大采集和生产临时写入必须单独授权。

### 外部记忆安全

- 增加常见明文凭据扫描；
- 增加 POSIX 目录 700、文件 600 权限收紧；
- 增加只读保留期候选报告，默认完成任务 90 天、临时分析 30 天建议值；
- 明确不默认同步到 OneDrive、NAS 或个人云盘，不自动删除用户文档。

### 验证

- 包校验新增复审控制器、路由用例、敏感信息负向测试、POSIX 权限和保留期报告测试；
- 真实 Codex 隐式 Skill 激活和 Windows PowerShell 实机安装保留为明确未验证项。

---

## 3.1.0 - 2026-07-29

### 新增

- 新增 `$log-observability-analysis` Skill；
- 新增静态文件、本地运行、远程非生产只读和生产只读四种日志分析模式；
- 新增日志清单、时区统一、异常聚类、跨服务时间线、证据分级和根因验证工作流；
- 新增日志分析报告、时间线和证据台账 3 个模板。

### 调整

- 全局 `AGENTS.md` 增加日志 Skill 自动调度和生产只读边界；
- Java、Python、数据基础设施、文档、交付和长期记忆 Skill 增加日志分析组合规则；
- 安装、验证、Manifest、触发矩阵和使用示例升级为 9 个 Skills；
- 明确简单只读日志分析不自动触发代码修复、Git、部署或多 Agent 代码复审。

### 安全

- 生产只读分析限制时间窗、行数、文件范围和查询成本；
- 禁止无限 `tail -f`、无边界递归扫描、Redis `KEYS *`、高消耗全表查询和未经授权的日志清理、重启或数据写入；
- 增加日志注入、敏感信息、压缩包路径穿越和解压膨胀风险约束。

---

## 3.0.0 - 2026-07-29

### 新增

- 新增 `$multi-agent-independent-review` Skill；
- 新增 7 个用户级或仓库级只读自定义 Reviewer；
- 新增复审计划、Reviewer 结果和归并台账模板；
- 新增持续检查点规则、恢复清单和检查点条目模板；
- 新增可选的 `checkpoint.py`，支持初始化、追加、校验、恢复、快照修复和热区归档；
- 新增 `config/agents.example.toml` 多 Agent 配置示例。

### 多 Agent 复审增强

- 条件允许时按风险并行启动 2～6 个职责不同的 Reviewer；
- 第一轮结果收齐前禁止边审边零散修改；
- 统一去重、根因聚类和冲突裁决后，形成最小完整修复集合并集中修复；
- 修复后只定向复核受影响范围，公共边界变化时扩大复核；
- 默认限制：递归深度 3、复审轮次 3、并行 Reviewer 6、单功能边界 Reviewer 总量 12、集中修复轮次 3；
- 达到上限后停止自动循环，如实保留阻塞和未验证项。

### 长期任务记忆增强

- 每个可独立恢复的小节点都更新 `CURRENT_TASK.md` 和 `PROGRESS.md`；
- 已完成节点不得只保存在聊天上下文中；
- 连续最多 5 个实质性动作必须形成检查点；
- 高风险操作采用写前与写后双检查点；
- 多 Agent 环境采用主协调 Agent 单一记忆写入者；
- 恢复时读取最近 5 个检查点，并核对分支、HEAD、工作区、代码、配置和验证证据；
- 明确 Codex Memories / Chronicle 只能作为辅助召回层，不能替代确定性任务文档；
- 检查点工具增加单写者锁、原子替换、Git 指纹核对、半写入修复和超限自动归档；
- 活跃进度默认保留最近 30 个检查点，恢复默认读取最近 5 个检查点。

### 安装与兼容

- 用户级默认安装全局规则、8 个 Skills 和 7 个 Reviewer；
- 新增 `ReviewAgentsOnly` / `agents` 独立安装和卸载模式；
- 仓库级安装可选择把 Reviewer 安装到 `.codex/agents`；
- 不自动修改 `config.toml`；
- 可直接覆盖升级 v1 / v2 同名 Skill，并备份原文件；
- 保留用户其他 Skills、自定义 Agent 和 `AGENTS.md` 非受管内容；
- 包校验新增 Reviewer TOML、检查点完整工作流、Git 状态漂移、修复、归档、重复安装和卸载隔离测试；
- 新增 `docs/V3_DESIGN_OVERVIEW.md`，说明多 Agent 复审与持续外部记忆的完整设计。

## 2.0.0 - 2026-07-28

### 新增

- 新增 `technical-document-writing` Skill；
- 新增正式技术文档规则、文档类型 Playbook 和 12 个模板；
- 新增用户级、仓库级卸载脚本；
- 新增 `validate-package.py` 包结构校验脚本。

### 改进

- 全局 `AGENTS.md` 默认采用受管区块合并，保留已有规则；
- 验证脚本覆盖 7 个 Skills、`openai.yaml`、受管区块和文档模板；
- 明确正式文档、CHANGELOG 和 Agent 外部记忆的职责边界。

## 1.0.0 - 2026-07-28

- 首次发布 Codex 跨项目长期技术助手 Skills 安装包。
