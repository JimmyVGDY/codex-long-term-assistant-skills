# Skill 自动触发与组合矩阵（v3.3）

## 零、最小充分加载策略

```text
PRIMARY_DOMAIN_SKILL_LIMIT = 1
DEFAULT_SUPPORTING_SKILL_LIMIT = 2
MAX_ACTIVE_SKILLS_WITHOUT_JUSTIFICATION = 4
```

1. 每个阶段先选择一个主领域 Skill；
2. 默认最多补充两个辅助 Skill；
3. 工作流 Skill 按阶段延迟激活，不在分析开始时提前加载全部交付、复审、文档和记忆规则；
4. 同时激活超过四个 Skill 时，必须说明每个 Skill 的唯一职责；
5. 当前阶段结束后，不再需要的 Skill 退出活动集合；
6. 请求方显式指定优先，但仍不得扩大权限和突破项目规则。

典型阶段：

```text
分析：领域 / 日志 Skill
→ 方案：必要时实施前复审
→ 实施：领域 + 质量交付
→ 稳定差异：实施后复审
→ 正式报告：文档 Skill
→ 跨会话：长期记忆
```

---

## 一、单 Skill 典型触发

| Skill | 应触发示例 | 通常不应单独触发 |
|---|---|---|
| `backend-engineering` | “分析 Spring 事务、FastAPI async、Fastify 或 Gin 服务端问题” | 纯 Vue 样式或纯 SQL 执行计划 |
| `frontend-engineering` | “修复路由切换后的请求竞态” | 纯数据库索引分析 |
| `ai-engineering` | “校验模型结构化输出、RAG 权限和 Agent 工具调用” | 不含模型行为的普通后端 Bug |
| `data-middleware-infrastructure` | “分析 Redis 热点 Key、数据库锁或 GPU 资源” | 普通服务端空指针说明 |
| `log-observability-analysis` | “分析这批本地日志并建立跨服务时间线” | 纯代码重构且没有日志输入 |
| `engineering-quality-delivery` | “修改后测试、复审并本地提交” | 只解释一个概念 |
| `multi-agent-independent-review` | “让多个 Reviewer 全面复审当前改动并减少回炉” | 无行为变化的文字修正 |
| `technical-document-writing` | “根据代码写正式架构设计文档” | 只改一条 Commit 信息 |
| `long-running-task-memory` | “任务跨多天，每个节点持续记录并可恢复” | 当前会话一次完成的小修复 |

## 二、推荐组合

| 任务 | 推荐组合 |
|---|---|
| 任意语言后端 Bug 修复 | 通用后端 + 质量交付；中高风险再加多 Agent 复审 |
| 后端 + Redis / MQ 修复 | 通用后端 + 数据基础设施 + 质量交付；高风险再加多 Agent 复审 |
| AI / RAG / GPU Worker 故障 | AI + 日志；按实际链路组合后端或数据基础设施，修改时加质量交付 |
| 前端与后端 SSE 全链路修复 | 通用前端 + 通用后端 + 数据基础设施 + 质量交付；高风险再加多 Agent 复审 |
| 基于代码写架构文档 | 文档 + 实际技术栈对应 Skill |
| 修改代码并同步正式方案 | 技术栈 + 质量交付 + 文档 |
| 跨会话大型改造 | 技术栈 + 质量交付 + 长期任务记忆；代码稳定后加多 Agent 复审 |
| 生产部署手册 | 文档 + 数据基础设施 + 质量交付 |
| 只读全方位审查 | 多 Agent 复审 + 对应技术栈 Skill |
| 多天生产观察 | 日志 + 长期任务记忆 + 对应技术领域；仅转入写操作时加质量交付 |


## 三、日志分析 Skill 触发测试

### 应触发

1. 分析本地目录中的多份应用日志和压缩日志包。
2. 根据 Docker、Kubernetes Pod 和 Nginx 日志建立故障时间线。
3. 只读分析生产 Java 服务、数据库连接池和 RabbitMQ 日志。
4. 根据 traceId 关联多个服务并区分根因与表象。
5. 对日志中的异常进行聚类、统计频率并给出验证步骤。

### 通常不应触发

1. 没有任何日志或可观测性数据的纯代码设计。
2. 只修改 README 标点。
3. 直接提出新增业务功能且不涉及故障证据。
4. 只解释一个与当前日志无关的理论概念。

### 模式选择

- 本地静态文件：允许受控解压和临时解析，不覆盖原文件；
- 本地运行环境：默认只读，重启和修改单独授权；
- 远程非生产：限制命令成本，不因非生产自动获得写权限；
- 生产只读：限制时间窗、行数和查询成本，禁止清理、重启、部署和数据写入。

## 四、多 Agent 复审触发测试

### 应触发

1. 当前改动涉及权限、公共接口、数据库和历史数据，请多开 Agent 全面复审。
2. 修复完成后从功能、回归、安全、性能、数据和并发角度独立检查。
3. 尽量一次找全问题，统一归因后集中修改，减少多次回炉。
4. 当前差异跨后端、前端和消息链路，需要并行只读审查。
5. 数据迁移即将提交，请执行严格独立复审。

### 通常不触发

1. 只修改 Markdown 标点。
2. 未修改代码，只解释异常含义。
3. 只拆分已有 Commit，不改变文件内容。
4. 明确限定只做一次局部自查且任务属于低风险非行为变更。

### 选择规则

- 低风险：0～1 个 Reviewer，默认 `economy` / Luna；
- 中风险：1～2 个 Reviewer，默认 `balanced`；
- 高风险：2～3 个 Reviewer，默认 `deep`，仅关键维度可 Terra High；
- 不为凑数量启动职责重复的 Reviewer；
- 第一轮未全部返回前不边审边改；
- 默认并行 3、累计 6、post 2 轮、修复 2 轮、Terra High 1 个；模型、人数、上下文和轮次同时受预算约束。

## 五、长期任务记忆触发测试

### 应触发

1. 任务预计跨多个会话或多个工作日。
2. 任务明确规定每完成一个小节点就更新任务和进度文档。
3. 多个 Agent 并行，必须确保上下文压缩后仍可继续。
4. 生产灰度需要连续观察和记录验证状态。
5. 当前对话已很长，后续仍有多个实施阶段。

### 小节点检查点

以下节点完成后立即更新 `CURRENT_TASK.md` 和 `PROGRESS.md`：

- 形成调用链结论；
- 确认或排除根因；
- 完成一组同功能边界修改；
- 完成构建、测试、迁移或样例验证；
- 派发、收齐或归并一轮 Reviewer；
- 完成集中修复或定向复核；
- 发生阻塞、范围变化、提交、部署或暂停。

单次 `ls`、`grep`、未形成结论的阅读和立即撤销的临时尝试不需要单独写检查点。

## 六、文档 Skill 触发测试

### 应隐式触发

1. 根据当前仓库写一份系统架构设计文档。
2. 把现有 Markdown 技术方案全面重构，保留业务口径。
3. 输出数据库表结构与索引设计文档。
4. 根据日志和代码写故障分析报告。
5. 整理成适合管理层讨论的正式项目报告。
6. 编写部署、灰度和回滚操作手册。
7. 写 API 接口设计和错误码说明。

### 通常不应单独触发

1. 给一个 Java 方法补一行注释。
2. 把 Commit 信息改成中文。
3. 只更新 CHANGELOG 中的一条记录。
4. 解释 Redis 缓存击穿。
5. 执行 `npm run build` 并报告结果。


## 七、实际 Codex 路由回归

包内提供：

- `tests/skill-routing-cases.json`：required / optional / forbidden / 最大活动 Skill；
- `scripts/routing-eval.py`：用例结构校验、观察模板生成和结果评分。

使用方式：

```bash
python3 scripts/routing-eval.py validate
python3 scripts/routing-eval.py make-template --output routing-observations.json
```

然后在 Codex 中逐条发送测试 Prompt，记录实际显示或报告的激活 Skill；不要根据期望值手工补齐。完成后：

```bash
python3 scripts/routing-eval.py evaluate --results routing-observations.json
```

包结构校验只能证明用例和工具有效，不能替代本机 Codex 的真实自动激活观察。每次修改 Skill 名称、description、全局调度规则或组合边界后都应重新执行。


## Reviewer 隔离调度补充

- TOML `read-only` 只表示配置声明；
- 父会话为 `danger-full-access` 或 `workspace-write` 时，默认只能标记 `logical-readonly`；
- 高风险、生产和严格只读任务必须使用整体只读父会话或有效系统隔离证据；
- 自查不能冒充独立 Reviewer，逻辑只读不能冒充系统隔离。

## V4.1 通用前端路由

| 场景 | 主 Skill | 辅助 Skill |
|---|---|---|
| Vue/Nuxt、React/Next/Remix、Preact、Angular、Svelte、Astro/Ember、传统/静态页面 | `frontend-engineering` | 修改时质量交付 |
| SSR/全栈前端服务端逻辑 | `frontend-engineering` | 对应后端与数据基础设施 |
| 微前端/Monorepo | `frontend-engineering` | 按修改组合质量/文档 |
| Hybrid Web / WebView / Renderer | `frontend-engineering` | 原生桥、主进程和系统能力另行审查 |
| Electron/Tauri 主进程、原生移动端 | 不使用 `frontend-engineering` | 按系统/后端/安全边界选择能力 |
| 纯 Node.js 后端 API/Worker | 不使用 `frontend-engineering` | `backend-engineering`；涉及数据库/MQ 时组合数据基础设施 |

## V7 四主领域路由

| 场景 | 主 Skill | 可选支撑 Skill |
|---|---|---|
| Java、Python、Node.js、Go、.NET、Rust 或其他服务端应用 | `backend-engineering` | 修改时质量交付；数据组件按需组合基础设施 |
| 浏览器、WebView、Renderer 与前端框架 | `frontend-engineering` | 后端、AI、数据按实际调用链组合 |
| 模型调用、RAG、Agent、AI 评测、推理与多模态生成 | `ai-engineering` | SDK/Worker 组合后端；向量库/GPU 资源组合基础设施 |
| 数据库、缓存、MQ、搜索/向量存储、文件、GPU 资源、容器和网络 | `data-middleware-infrastructure` | 应用调用方组合后端；AI 语义组合 AI |

同一阶段只选一个主领域。项目使用 Python 不等于 AI，项目名称包含 AI 也不等于当前任务应触发 AI；`package.json` 不等于前端，纯 Node.js 服务端必须路由通用后端。
