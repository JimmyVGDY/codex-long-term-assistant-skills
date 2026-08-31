# Codex 跨项目长期技术助手 Skills 安装包 v3.2

本包把跨项目工程规则安装为 Codex 原生 Skills、全局 `AGENTS.md` 受管规则和只读自定义 Reviewer。v3.2 在 v3.1 基础上完成 P0 级确定性增强：最小充分 Skill 调度、实施前设计门禁、复审状态控制器、多信号可观测性、外部记忆安全治理和路由回归测试。

1. **最小充分 Skill 调度**：每个阶段只加载一个主领域 Skill 和最少必要的辅助 Skill，减少规则竞争与上下文膨胀；
2. **实施前与实施后双门禁**：高风险方案编码前先审查方向，代码完成后再执行独立复审；
3. **确定性多 Agent 复审**：通过状态控制器记录 Reviewer 轮次、深度、数量和修复预算，减少上下文压缩后的失控；
4. **多信号可观测性**：统一分析 Logs、Metrics、Traces、Profiles、Alerts 和变更事件；
5. **持续且安全的外部记忆**：每个可恢复小节点持久化，同时增加敏感信息、权限和保留期治理；
6. **Skill 路由回归**：使用代表性任务验证自动触发范围，防止 Skill 越加越多后出现误触发和过度加载。

安装脚本默认保留用户已有规则、第三方 Skills 和其他自定义 Agent，不修改 `config.toml`，不执行 Git、部署、重启或生产写操作。

---

## 一、v3.2 核心变化

### 1.1 最小充分 Skill 调度

默认参数：

```text
PRIMARY_DOMAIN_SKILL_LIMIT = 1
DEFAULT_SUPPORTING_SKILL_LIMIT = 2
MAX_ACTIVE_SKILLS_WITHOUT_JUSTIFICATION = 4
```

主 Agent 每个阶段先选择一个主领域 Skill，默认最多补充两个辅助 Skill；超过四个活动 Skill 时必须说明每个 Skill 的唯一职责。工作流 Skill 按分析、方案、实施、复审、文档和长期恢复阶段延迟激活。

### 1.2 实施前与实施后双复审门禁

高风险公共契约、数据库迁移、权限、核心状态机、跨服务、高并发和生产迁移在编码前优先执行一次实施前设计与影响审查，默认 2～4 个 Reviewer。代码和最低定向验证稳定后，仍执行实施后独立复审；两者不能互相替代，全部 Reviewer 共同受累计 12 个预算限制。

### 1.3 复审状态控制器

新增：

```text
skills/multi-agent-independent-review/scripts/review_controller.py
```

控制器不创建 Agent、不修改代码，只持久化 pre/post 阶段、轮次、深度、派发、结果、归并、修复轮次和剩余 Reviewer 预算。上下文压缩后必须先读取状态，不能仅凭聊天记忆继续派生。

### 1.4 日志与可观测性分析 Skill

现有 Skill：

```text
$log-observability-analysis
```

覆盖四种模式：

1. 静态本地/上传日志文件；
2. 本地运行环境；
3. 远程非生产只读；
4. 生产只读。

主要能力包括日志清单、时区统一、异常聚类、跨服务时间线、trace/request/task ID 关联、证据分级、候选根因、验证步骤、敏感信息脱敏和大文件资源控制。日志分析不自动获得代码修改、清理、重启、部署或生产写权限。

提供 6 个模板：日志报告、事件时间线、证据台账、Metrics 分析、Trace 分析和多证据源关联。

### 1.5 多 Agent 独立复审 Skill

现有 Skill：

```text
$multi-agent-independent-review
```

默认工作流：

```text
稳定 git diff
    ↓
按风险选择 1～6 个不同职责的只读 Reviewer
    ↓
等待本轮结果全部返回
    ↓
主协调 Agent 去重、根因聚类、冲突裁决和分级
    ↓
形成最小完整修复集合
    ↓
集中修复
    ↓
重跑受影响验证并定向复核
```

默认安全上限：

```text
MAX_REVIEW_AGENT_DEPTH = 3
MAX_PREIMPLEMENTATION_REVIEW_ROUNDS = 1
MAX_PREIMPLEMENTATION_REVIEWERS = 4
MAX_POST_REVIEW_ROUNDS = 3
MAX_PARALLEL_REVIEWERS = 6
MAX_TOTAL_REVIEW_AGENTS_PER_BOUNDARY = 12
MAX_REPAIR_ROUNDS = 3
```

达到任一上限后停止自动循环，保留阻塞项和未验证项，不得为了结束流程伪称通过。

### 1.6 7 个只读专业 Reviewer

| Reviewer | 主要职责 |
|---|---|
| `cp_review_functional_business` | 功能正确性、业务口径、状态流转、异常与补偿 |
| `cp_review_compatibility_regression` | 原有功能回归、旧接口、旧数据和新旧版本共存 |
| `cp_review_security_access` | 认证、鉴权、越权、注入、文件和敏感信息 |
| `cp_review_performance_resources` | SQL、I/O、线程、连接、队列、内存和资源负担 |
| `cp_review_data_contract` | 数据库、API、Redis、MQ、序列化和契约一致性 |
| `cp_review_state_concurrency` | 并发、幂等、超时、重试、取消、恢复和交互状态 |
| `cp_review_test_delivery` | 测试证据、验证缺口、CHANGELOG、提交和授权边界 |

这些 Reviewer 均配置为 `read-only`，不修改文件、不提交、不推送、不部署、不重启、不写数据，也不继续派生其他 Agent。

### 1.7 长期任务记忆持续检查点

启用 `$long-running-task-memory` 后：

- 每完成一个可独立恢复的小节点，立即追加 `PROGRESS.md` 并刷新 `CURRENT_TASK.md`；
- 已完成节点不得只存在于聊天上下文；
- 尚未形成完整节点时，连续最多 5 个实质性动作必须写一次“进行中检查点”；
- 高风险或可能部分成功的操作，在操作前和操作后分别写检查点；
- 多 Agent 场景只允许主协调 Agent 写共享记忆；
- 恢复时默认读取最近 5 个检查点，并核对分支、HEAD、工作区、代码、配置和验证证据；
- 活跃进度建议控制在 30 个检查点以内，旧记录归档到 `archive/`；
- Codex Memories / Chronicle 仅作为辅助召回，不替代确定性任务文档。

### 1.8 检查点辅助脚本

```text
skills/long-running-task-memory/scripts/checkpoint.py
```

支持：

- `init`：初始化任务快照、计划、进度、复审和归档目录；
- `append`：追加持久化检查点并刷新当前任务；
- `validate`：核对检查点 ID、状态版本和可选 Git 指纹；
- `recover`：输出当前状态和最近检查点恢复摘要；
- `repair`：在进度已追加但当前快照未成功刷新时，根据最后检查点修复快照；
- `archive`：把超出热区上限的旧检查点归档；
- `security-check`：扫描常见明文凭据模式并检查 POSIX 权限；
- `secure`：在 POSIX 上收紧目录和文件权限；
- `retention-report`：只读列出超过保留期的归档候选，不自动删除。

脚本只使用 Python 标准库，默认拒绝把外部记忆写入 Git 工作区。

### 1.9 多信号可观测性

`$log-observability-analysis` 现覆盖 Logs、Metrics、Distributed Traces、Profiles / Dumps、Alerts 和发布/配置变更事件。在线 Profiling、扩大采集范围和生产临时写入仍需单独授权。

### 1.10 外部记忆安全与生命周期

- 最小必要信息和常见明文凭据扫描；
- Linux/WSL 目录 700、文件 600 建议；Windows ACL 需本机确认；
- 已完成任务默认 90 天、临时分析默认 30 天建议值；
- 不默认同步到 OneDrive、NAS 或个人云盘；
- 保留期命令只报告候选，不自动删除。

### 1.11 Skill 路由回归

新增 `tests/skill-routing-cases.json` 和 `scripts/routing-eval.py`。包校验验证用例结构；真实自动激活结果必须在本机 Codex 中逐条观察和评分，静态检查不能冒充运行验证。

---

## 二、安装包结构

```text
Codex跨项目长期技术助手Skills安装包_v3.2_P0确定性增强版/
├── global/
│   └── AGENTS.md
├── skills/
│   ├── java-backend-engineering/
│   ├── python-backend-ai-engineering/
│   ├── vue-frontend-engineering/
│   ├── data-middleware-ai-infrastructure/
│   ├── log-observability-analysis/
│   ├── engineering-quality-delivery/
│   ├── multi-agent-independent-review/
│   ├── technical-document-writing/
│   └── long-running-task-memory/
├── custom-agents/
│   └── 7 个只读 Reviewer TOML
├── config/
│   └── agents.example.toml
├── scripts/
│   ├── install-user.*
│   ├── verify-user-install.*
│   ├── uninstall-user.*
│   ├── install-repo-skills.*
│   ├── uninstall-repo-skills.*
│   ├── routing-eval.py
│   └── validate-package.py
├── docs/
├── tests/
│   └── skill-routing-cases.json
├── examples/
├── manifest.json
└── CHANGELOG.md
```

用户级默认目标：

```text
全局规则       ${CODEX_HOME:-$HOME/.codex}/AGENTS.md
Skills         $HOME/.agents/skills/<skill-name>/
自定义 Agent   ${CODEX_HOME:-$HOME/.codex}/agents/*.toml
```

仓库级默认目标：

```text
<repo>/.agents/skills/<skill-name>/
<repo>/.codex/agents/*.toml       # 仅显式要求时安装
```

---

## 三、包含的 Skills

| Skill | 主要触发场景 |
|---|---|
| `$java-backend-engineering` | Java、Spring、Struts2、MyBatis、事务、并发、JVM、SSE |
| `$python-backend-ai-engineering` | Python Web、异步、多进程、Celery、AI、RAG、GPU Worker |
| `$vue-frontend-engineering` | Vue、路由、状态、请求竞态、SSE、WebSocket、构建 |
| `$data-middleware-ai-infrastructure` | SQL、Redis、MQ、ES、文件、对象存储、RAG、Docker、K8s |
| `$log-observability-analysis` | 日志、Metrics、Trace、Profiling、告警、变更事件和生产只读分析 |
| `$engineering-quality-delivery` | 修改、测试、最低定向验证、Git、部署、生产安全 |
| `$multi-agent-independent-review` | 实施前设计门禁、实施后多 Reviewer 复审、集中归因和确定性预算 |
| `$technical-document-writing` | 技术方案、架构、接口、数据库、部署、报告和 Markdown 重构 |
| `$long-running-task-memory` | 跨会话、多阶段、多 Agent、持续检查点和上下文恢复 |

Skills 会按描述自动匹配；高风险任务建议用 `$skill-name` 显式指定。

---

## 四、日志分析使用示例

### 本地日志文件

```text
使用 $log-observability-analysis。
分析当前目录中的应用日志和压缩日志包，先确认时区、文件范围和完整性，
建立异常聚类和时间线；不要覆盖原文件，输出时脱敏。
```

### 生产只读日志

```text
使用 $log-observability-analysis 和对应技术栈 Skill。
仅在生产执行只读日志、监控和低风险状态分析，限制时间窗口和行数。
禁止修改、清理、重启、部署、切流和任何数据写操作。
```

### 跨服务长期排障

```text
使用 $log-observability-analysis 和 $long-running-task-memory。
按服务和组件并行只读分析，由主 Agent 统一时区、归并时间线和证据台账；
每完成一个可恢复节点更新 CURRENT_TASK.md 和 PROGRESS.md。
```

## 五、Windows 用户级安装

### 5.1 完整解压

不要直接在压缩包预览窗口中运行脚本。进入解压后的安装包根目录，确认能看到：

```text
README.md
custom-agents
config
global
skills
scripts
```

### 5.2 安装全部组件

```powershell
powershell -ExecutionPolicy Bypass -File ".\scripts\install-user.ps1"
```

默认安装：

- 全局 `AGENTS.md` 受管区块；
- 9 个用户级 Skills；
- 7 个用户级只读 Reviewer。

从 v1、v2、v3.0 或 v3.1 升级不需要先卸载。脚本会备份同名旧文件并更新本包管理的内容。

### 5.3 分组件安装

仅安装 Skills：

```powershell
powershell -ExecutionPolicy Bypass -File ".\scripts\install-user.ps1" -Component SkillsOnly
```

仅安装全局规则：

```powershell
powershell -ExecutionPolicy Bypass -File ".\scripts\install-user.ps1" -Component GlobalOnly
```

仅安装 Reviewer：

```powershell
powershell -ExecutionPolicy Bypass -File ".\scripts\install-user.ps1" -Component ReviewAgentsOnly
```

只有明确希望整体替换现有全局文件时才使用：

```powershell
powershell -ExecutionPolicy Bypass -File ".\scripts\install-user.ps1" `
  -Component GlobalOnly `
  -ForceReplaceGlobal
```

正常升级不要使用 `-ForceReplaceGlobal`。

### 5.4 验证

```powershell
powershell -ExecutionPolicy Bypass -File ".\scripts\verify-user-install.ps1"
```

### 5.5 卸载本包

```powershell
powershell -ExecutionPolicy Bypass -File ".\scripts\uninstall-user.ps1"
```

也可以通过 `-Component` 只卸载 Skills、全局受管区块或 Reviewer。卸载不会删除其他第三方资源。

---

## 六、WSL / Linux 用户级安装

```bash
chmod +x scripts/*.sh scripts/validate-package.py
./scripts/install-user.sh
./scripts/verify-user-install.sh
```

分组件安装：

```bash
./scripts/install-user.sh skills
./scripts/install-user.sh global
./scripts/install-user.sh agents
```

卸载：

```bash
./scripts/uninstall-user.sh
```

Windows 原生 Codex 与 WSL 中的 Codex 通常使用不同的 `$HOME`。在哪个环境运行 Codex，就在对应环境安装。

---

## 七、安装到单个仓库

仅安装仓库级 Skills：

```powershell
powershell -ExecutionPolicy Bypass -File ".\scripts\install-repo-skills.ps1" `
  -RepoPath "D:\projects\your-repo"
```

同时安装仓库级 Reviewer：

```powershell
powershell -ExecutionPolicy Bypass -File ".\scripts\install-repo-skills.ps1" `
  -RepoPath "D:\projects\your-repo" `
  -IncludeReviewAgents
```

WSL / Linux：

```bash
./scripts/install-repo-skills.sh /path/to/your-repo
./scripts/install-repo-skills.sh /path/to/your-repo --include-review-agents
```

仓库级资源位于 `.agents/` 和可选的 `.codex/` 中，是否提交 Git 必须由项目规范决定。外部任务记忆本身仍应保存在仓库外。

---

## 八、可选多 Agent 配置

安装脚本不会修改 `config.toml`。需要显式限制并发时，可参考：

```text
config/agents.example.toml
```

核心示例：

```toml
[agents]
enabled = true
max_concurrent_threads_per_session = 6
```

该配置只是平台并发上限。本包仍会根据任务风险选择 1～6 个不同职责的 Reviewer，并遵守单功能边界累计 12 个 Reviewer、最多 3 轮复审和 3 轮集中修复的内部约束。

---

## 九、典型使用方式

### 9.1 Java 修复、持续检查点和多 Agent 复审

```text
使用 $java-backend-engineering、$engineering-quality-delivery、
$multi-agent-independent-review 和 $long-running-task-memory。

完整阅读当前调用链后修复问题。每完成一个可恢复小节点就更新
CURRENT_TASK.md 和 PROGRESS.md。相关定向测试完成后，根据风险并行启动
不同职责的只读 Reviewer；本轮结果全部收齐前不要零散修改。
统一归因后集中修复，最多 3 轮。更新 CHANGELOG，创建本地提交但不要推送。
```

### 9.2 只读多 Agent 复审

```text
使用 $multi-agent-independent-review。

只读审查当前分支相对基线的差异。按功能、兼容、安全、性能、数据、
状态并发和测试交付维度选择必要 Reviewer。等待本轮全部返回后统一去重、
根因聚类和分级。不要修改文件、提交、推送、部署或重启。
```

### 9.3 跨会话大型改造

```text
使用 $long-running-task-memory、$engineering-quality-delivery
和当前技术栈对应 Skills。

先恢复或初始化外部任务文档。把对话上下文视为短期缓存；每完成一个
可独立恢复的小节点立即写检查点。任何上下文压缩、模型切换或暂停后，
先核对外部文档与当前 Git、代码、配置和验证证据，再继续下一步。
```

更多示例见 `examples/usage-prompts.md`。

---

## 十、检查点辅助脚本示例

初始化外部记忆目录：

```bash
python3 skills/long-running-task-memory/scripts/checkpoint.py init \
  --project-dir "/path/outside/repo/project-context/TASK-001" \
  --task-id "TASK-001" \
  --title "修复订单状态回写" \
  --repo-path "/path/to/repo"
```

追加节点：

```bash
python3 skills/long-running-task-memory/scripts/checkpoint.py append \
  --project-dir "/path/outside/repo/project-context/TASK-001" \
  --task-id "TASK-001" \
  --stage "A2" \
  --node-type "验证" \
  --summary "订单状态回写相关 Service 定向测试通过" \
  --validation "执行 ./mvnw -Dtest=OrderServiceTest test，结果通过" \
  --next-action "启动功能、兼容、数据和并发四个只读 Reviewer" \
  --repo-path "/path/to/repo"
```

校验与恢复：

```bash
python3 skills/long-running-task-memory/scripts/checkpoint.py validate \
  --project-dir "/path/outside/repo/project-context/TASK-001" \
  --repo-path "/path/to/repo" \
  --strict-git

python3 skills/long-running-task-memory/scripts/checkpoint.py recover \
  --project-dir "/path/outside/repo/project-context/TASK-001" \
  --repo-path "/path/to/repo" \
  --recent 5
```

脚本是可选辅助工具。Agent 即使不调用脚本，也必须遵守同等的检查点与恢复规则。

---

## 十一、复审状态控制器示例

```bash
python3 skills/multi-agent-independent-review/scripts/review_controller.py init \
  --review-dir "/path/outside/repo/project-context/TASK-001/reviews/FB-001" \
  --boundary-id "FB-001" --title "订单状态回写"

python3 skills/multi-agent-independent-review/scripts/review_controller.py plan \
  --review-dir "/path/outside/repo/project-context/TASK-001/reviews/FB-001" \
  --phase pre --depth 1 \
  --reviewers "cp_review_functional_business,cp_review_data_contract" \
  --purpose "实施前方案与契约审查"
```

完整命令包括 `init / plan / dispatch / result / merge / repair / validate / status / close`。

## 十二、Skill 路由回归

```bash
python3 scripts/routing-eval.py validate
python3 scripts/routing-eval.py make-template --output routing-observations.json
# 在 Codex 中逐条运行并记录实际 activated
python3 scripts/routing-eval.py evaluate --results routing-observations.json
```

## 十三、包结构校验

安装前可执行：

```powershell
python .\scripts\validate-package.py
```

```bash
python3 ./scripts/validate-package.py
```

校验覆盖：

- `manifest.json` 与 9 个 Skills；
- Skill Frontmatter、`agents/openai.yaml` 和相对引用；
- 7 个自定义 Agent 的 TOML、只读沙箱和必需字段；
- 全局 `AGENTS.md` 受管标记、关键规则和大小；
- 12 个正式文档模板、10 个外部记忆模板、4 个复审模板和 6 个可观测性模板；
- 检查点脚本的初始化、追加、校验、恢复、修复、归档、安全扫描、权限收紧、保留期报告和 Git 指纹保护；
- 复审状态控制器的 pre/post 轮次、深度、派发、归并、修复和总预算；
- Skill 路由用例和观察工具结构；
- Shell 脚本语法；
- PowerShell 可用时执行解析器检查，不可用时执行静态结构检查；
- Markdown 代码块、硬编码个人路径和包结构。

实际验证结果见 `docs/VALIDATION_REPORT.md`；P0 设计见 `docs/P0_OPTIMIZATION_DESIGN.md`，路由评测见 `docs/SKILL_ROUTING_EVAL.md`，基础设计见 `docs/V3_DESIGN_OVERVIEW.md`。

---

## 十四、安全与边界

- 默认合并全局受管区块，不覆盖其他个人或公司规则；
- 安装、升级和卸载前默认备份；
- 只覆盖本包同名 Skills 和 Reviewer；
- 不自动修改 `config.toml`、模型、MCP、网络和权限；
- Reviewer 为只读，不能借复审扩大写权限；
- 外部任务记忆不得进入项目仓库、Git 和项目 CHANGELOG；
- 文档状态不能替代实际代码、测试、运行结果和环境验证；
- 多 Agent 会增加 Token 和协调成本，因此只按风险启用不同职责 Reviewer，不为凑数量重复审查；
- Windows PowerShell 脚本应在本机运行 `verify-user-install.ps1` 完成最终环境验证。
