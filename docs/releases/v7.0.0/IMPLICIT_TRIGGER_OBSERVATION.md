# V7.0.0 真实隐式触发观察

English: [IMPLICIT_TRIGGER_OBSERVATION.en.md](IMPLICIT_TRIGGER_OBSERVATION.en.md)

观察日期：2026-09-01

观察范围：Codex CLI 0.150.1、`gpt-5.6-luna`、`low` 推理强度、四个只读场景。

## 结论

四个代表性场景均在未显式点名目标 Skill 的情况下命中预期领域路由；随后完成的完整 Plugin 升级也由全新只读任务命中通用后端与数据基础设施组合路由。真实隐式触发观察 PASS。该结论只覆盖本报告中的场景，不等于所有自然语言变体都能确定性命中。

## 观察方法

1. 安装前确认 `$HOME/.agents/skills` 下四个目标目录均不存在。
2. 仅临时复制 `$backend-engineering`、`$ai-engineering`、`$frontend-engineering` 和 `$data-middleware-infrastructure`，不安装 AGENTS、Hooks、Reviewer 或其他 Skill。
3. 在不含仓库级 Skill 的干净临时 Git 仓库中，以 `--ephemeral --ignore-user-config --ignore-rules` 运行四次独立只读任务。
4. 提示词只描述工程场景，不显式指定应采用哪个 Skill；任务末尾报告实际采用的 Skill。
5. 观察完成后删除四个临时账号级目录，并读回确认它们与所有观察目录均不存在。

## 结果

| 场景 | 预期路由 | 实际报告 | 结果 |
| --- | --- | --- | --- |
| Node.js 订单状态、PostgreSQL 事务、RabbitMQ、幂等与兼容 | 后端 + 数据基础设施 | `backend-engineering,data-middleware-infrastructure` | PASS |
| 语言无关的 RAG、结构化输出、引用、评测与幻觉控制 | AI | `ai-engineering` | PASS |
| 多模态推理 Worker、GPU 配额、队列背压、对象存储与评测 | AI + 数据基础设施 | `ai-engineering,data-middleware-infrastructure` | PASS |
| React 多步骤表单、可访问性、响应式与客户端状态恢复 | 前端 | `frontend-engineering` | PASS |

## 完整 Plugin 升级读回

- 在 Windows 原生 Codex CLI 0.150.1 上从受管 6.6.0 升级到 7.0.0：PASS。
- Codex CLI 读回 `installed=true`、`enabled=true`、`version=7.0.0`：PASS。
- 源码、Marketplace 与 Plugin cache 均为 182 个 payload 文件，digest 一致：PASS。
- 10 个 Skill、7 个 Reviewer、6 个 Hook 及唯一一组 AGENTS 受管标记：PASS。
- `config.toml` SHA-256 升级前后一致，原有 34 个账号级第三方 Skill 保留，四个 Manifest 声明的旧 Skill 不存在：PASS。
- 全新只读 Codex 任务报告 `backend-engineering,data-middleware-infrastructure`：PASS。

## 证据边界

- 仓库级 `.agents/skills` 的早期尝试因宿主访问拒绝而未加载 V7 Skill，其 `NONE` 或其他 Skill 结果仍判定为无效观察，不纳入 PASS。
- 最初四类观察来自标准账号级 Skill 目录的成功加载及各任务最终输出的 `ACTIVATED_SKILLS` 报告；完整 Plugin 升级后的新任务提供了第二层宿主证据。两者都不是底层路由器的独立 Trace。
- 命令指定了 `gpt-5.6-luna` 与 `low`，但未通过外部提供商 Trace 独立证明实际模型。
- 完整 Plugin 验收使用当前源码树，而不是尚未生成的公开 Release ZIP；公开制品仍需独立来源证明和下载后验收。
- Git 提交、推送、公开发布、重启和生产写入不由本报告证明，必须在各自动作后独立读回。
- 恢复验证：四个账号级临时 Skill 目录、两个仓库观察目录及已知系统临时观察目录均已不存在。
