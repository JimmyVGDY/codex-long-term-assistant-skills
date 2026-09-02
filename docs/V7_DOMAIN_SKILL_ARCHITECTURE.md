# V7.3 当前领域 Skill 架构与路由矩阵

> 状态：`active`。V7 建立了职责型主领域，V7.3 沿用并验证以下当前路由。

## 一、目标

V7.3 的主领域 Skill 按工程职责分类：

```text
backend-engineering
frontend-engineering
ai-engineering
data-middleware-infrastructure
```

语言、框架、模型提供方和基础设施产品只作为渐进加载的专项 Reference，不再决定顶层 Skill 名称。这样可覆盖现有 Java、Python 和 Web 技术栈，也能在不继续增加主 Skill 的情况下兼容 Node.js、Go、.NET、Rust、PHP、Ruby 等后端。

## 二、职责矩阵

| 主领域 Skill | 主责 | 按需加载 | 不负责 |
|---|---|---|---|
| `backend-engineering` | 服务端接口、业务分层、认证鉴权、应用事务语义、并发与任务、容错、资源生命周期、服务端测试 | Java/Spring/JVM、Python Web/异步、Node.js、Go、.NET、Rust 和其他服务端专项 | 浏览器交互；数据库引擎、MQ 集群和容器平台运维；模型质量与 RAG 评测 |
| `frontend-engineering` | 浏览器、WebView、桌面 Renderer、状态、路由、表单、异步竞态、安全、性能、构建和交互验证 | Vue、React、Angular、Svelte、传统页面、微前端和混合 Renderer 专项 | 纯服务端、数据库或模型推理任务；桌面主进程和原生系统能力 |
| `ai-engineering` | 模型调用契约、结构化输出、Prompt 安全、RAG、Agent 工具调用、评测、成本、降级、生成任务状态与恢复 | 托管模型、私有推理、RAG、Agent、GPU/多模态和 AI 质量专项 | 普通服务端业务规则；数据库/向量库引擎运维；GPU/Kubernetes 资源供应与集群操作 |
| `data-middleware-infrastructure` | 数据库、事务锁、Redis、消息队列、搜索与向量存储、文件与对象存储、GPU 资源、容器、Kubernetes 和网络 | 按数据库、中间件、存储、运行环境和资源类型加载 | 普通应用业务代码、浏览器交互、模型输出正确性和 Prompt/RAG 业务语义 |

## 三、交叉边界裁定

| 场景 | 主 Skill | 可选支撑 Skill | 裁定依据 |
|---|---|---|---|
| ORM Session、应用事务编排、接口幂等 | `backend-engineering` | `data-middleware-infrastructure` | 应用成功边界归后端；SQL、锁和数据库机制归数据基础设施 |
| SQL、索引、DDL、数据库锁与迁移执行 | `data-middleware-infrastructure` | `backend-engineering` | 数据引擎行为是主问题；仅在需要追踪应用调用方时加载后端 |
| 模型 API、结构化输出、Prompt 注入、模型降级 | `ai-engineering` | `backend-engineering` | 模型行为与输出可信度是主问题；HTTP 接口和应用状态可由后端支撑 |
| RAG 召回、权限过滤、引用和评测 | `ai-engineering` | `data-middleware-infrastructure` | 检索质量与权限语义归 AI；向量库容量、索引和运行归数据基础设施 |
| GPU Worker 任务状态、取消和恢复 | `ai-engineering` | `backend-engineering`、`data-middleware-infrastructure` | AI 任务语义归 AI；Worker 应用机制归后端；显存与集群资源归基础设施 |
| AI 流式页面、生成进度和交互竞态 | `frontend-engineering` | `ai-engineering`、`backend-engineering` | 浏览器状态和体验归前端；模型与服务端契约按实际链路支撑 |

每个阶段仍只选择一个主领域 Skill，默认最多组合两个支撑 Skill。一个任务跨多个阶段时允许更换主 Skill，不为覆盖整条链路同时加载全部领域。

## 四、后端渐进加载

`backend-engineering` 先读取通用核心，再根据当前项目证据最多加载一个主要技术栈专项：

- Java / Spring / JVM；
- Python Web / async / Worker；
- Node.js / TypeScript 服务端；
- Go 服务端；
- .NET 服务端；
- Rust 服务端；
- 其他或无法识别的服务端。

无法识别技术栈时只使用通用规则并明确未验证项，不把已知框架语义强行套入未知项目。混合后端仓库先按应用目录和进程边界划分，再为当前子任务加载对应专项。

## 五、AI 渐进加载

`ai-engineering` 将跨语言规则放在通用核心，并按任务加载：

- 模型提供方与结构化输出；
- RAG、检索权限和评测；
- Agent 与工具调用；
- GPU、推理 Worker 和多模态生成；
- AI 质量、成本、可观测性和安全。

语言 SDK 的异常、并发和资源管理仍由相应后端专项处理；向量数据库、对象存储、GPU 资源和容器集群的运行机制仍由数据基础设施 Skill 处理。

## 六、正负路由基线

### 应触发 `backend-engineering`

- Spring 事务自调用、FastAPI async 阻塞、Fastify 中间件、Gin 请求生命周期、ASP.NET Core DI、Axum 状态共享；
- Node.js、Go、.NET、Rust 或混合语言后端的接口、业务状态、任务和并发问题；
- 不涉及具体语言但明确属于服务端应用的架构、代码审查和故障修复。

### 不应触发 `backend-engineering`

- 纯 SQL 执行计划、Redis 集群、RabbitMQ 运维、Kubernetes 资源或对象存储问题；
- 纯浏览器组件、样式、路由和交互问题；
- 单纯模型 Prompt、RAG 评测或 Agent 工具设计，且不涉及服务端实现。

### 应触发 `ai-engineering`

- 模型调用、结构化输出、Prompt 注入、RAG、Agent、模型评测、Token 成本和模型降级；
- AI Worker 的生成状态、取消、失败恢复、GPU 推理和多模态任务语义。

### 不应触发 `ai-engineering`

- 普通 Python/Java/Node/Go 服务端逻辑中没有模型、检索或推理行为的任务；
- 单纯数据库、向量库或 GPU 集群容量运维；
- 仅因项目名称含有 AI，但当前修改与 AI 链路无关。

## 七、升级与兼容策略

V7 不安装旧 Skill 的兼容别名。安装或升级时对以下受管旧目录执行“先备份、后移除、再安装新 Skill”的迁移：

- `java-backend-engineering`；
- `python-backend-ai-engineering`；
- `data-middleware-ai-infrastructure`；
- 已有的 `vue-frontend-engineering`。

第三方同名以外的未知 Skill 不得删除。升级后发现旧目录残留、新旧 Skill 同时可发现或新 Skill 缺失时，验证失败关闭。

## 八、验收标准

1. 中文和英文发行均只包含十个唯一 Skill，四个主领域名称一致；
2. 旧三个领域 Skill 不再出现在安装源、Plugin 载荷或安装后 Skill 列表；
3. Java、Python 规则无实质丢失，并能通过后端专项按需发现；
4. Node.js、Go、.NET、Rust、混合后端、纯 AI 与 AI+GPU 路由用例通过；
5. 双语审计、语义校验、包验证、安装/恢复和确定性发行验证通过；
6. 最后在真实 Codex 宿主中观察隐式触发，包内回归不能替代宿主证据。
