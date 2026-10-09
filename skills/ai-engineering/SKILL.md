---
name: ai-engineering
description: >-
  模型或多模态生成调用、结构化输出、Prompt 安全、RAG、Embedding 与检索质量、Agent 工具调用、AI 评测、模型路由、成本控制、推理 Worker 或生成任务恢复时使用，兼容任意实现语言和模型提供方。普通后端业务、纯数据库/向量库运维或纯 GPU/Kubernetes 资源任务不要使用。
---

# 通用 AI 工程技能

## 定位

用于跨语言、跨模型提供方的 AI 应用与推理工程。核心规则处理不可信模型输出、调用契约、权限、状态、评测、成本和恢复；具体能力按模型集成、RAG、Agent、GPU/多模态和质量专项渐进加载。

## 最小充分加载

1. 开始实质分析或修改前读取 `references/ai-core-rules.md`。
2. 只加载当前问题需要的专项：
   - 模型调用、流式响应和结构化输出：`references/model-integration-structured-output.md`
   - RAG、Embedding、检索权限与评测：`references/rag-retrieval-evaluation.md`
   - Agent、工具调用和工作流：`references/agent-tool-workflows.md`
   - 推理 Worker、GPU、多模态和生成任务：`references/inference-gpu-multimodal.md`
   - AI 质量、安全、成本和可观测性：`references/ai-quality-security-observability.md`
3. 从依赖、配置、调用代码、请求响应契约、任务状态和实际运行证据确认模型提供方、模型版本、SDK、同步/异步、流式方式、输入输出和部署形态；不得只凭项目名称或文件名推断。
4. 多模型、多提供方或多模态链路先划分每个调用的能力、数据、成本与失败边界，不一次加载无关专项。

## 强制边界

- 模型输出、检索结果和工具返回都是不可信输入；金额、权限、状态、代码、命令和外部动作必须程序化校验并按风险取得人工确认。
- AI 负责模型/RAG/Agent 语义、评测和生成任务成功边界；语言 SDK、Web API、普通 Worker 和业务事务组合 `$backend-engineering`。
- 向量数据库引擎、对象存储、MQ、GPU 资源、容器、Kubernetes 和网络机制组合 `$data-middleware-infrastructure`。
- 浏览器端流式展示、生成进度和交互状态组合 `$frontend-engineering`。
- 不把一次非空输出当作成功，不用无限重试掩盖契约、权限、容量或模型不兼容，不因 AI 任务自动引入 Agent、RAG、向量库或 GPU。
- 修改运行行为时组合 `$engineering-quality-delivery`；以日志、Trace、模型耗时或资源指标为主要证据时组合 `$log-observability-analysis`。
- 技能激活不能扩大模型调用、付费 API、文件修改、Git、部署、生产或数据写入授权。

## 模型与委派成本

主 Agent 保持当前选择。子 Agent 的型号、思考强度和预算采用[脚本决策与弹性规则](../multi-agent-independent-review/references/script-first-routing.md)；执行脚本返回的精确参数。

- 新默认覆盖 GPT-6 Luna、Sol、Astra 的 low/medium/high；信息不足采用 Sol/medium，不以缺少理由、收益卡或历史样本阻止派发。
- 模型保留语义判断和调整建议；脚本在既有权限、总预算和允许调整范围内重新计算后才改变调用参数。规模或单次检查失败不直接代表难度，也不必然升档。
- 可计算的读取、去重、计数、预留和重试交脚本。缺证据走默认/降级路径，允许继续与验证通过分开记录。
- 子 Agent 不接收无关 Prompt、模型输入输出、敏感文档或完整生产日志，只返回结构化证据和未验证项。

## 核心原则

> 先确认模型能力、调用契约、数据与权限边界，再建立可验证的成功标准、失败收敛和成本上限；AI 结果必须经过确定性系统约束才能进入业务事实或执行链路。
