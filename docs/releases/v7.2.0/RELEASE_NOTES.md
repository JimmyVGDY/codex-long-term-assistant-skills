# V7.2.0 发行说明

English: [RELEASE_NOTES.en.md](RELEASE_NOTES.en.md)

版本：7.2.0

## 核心变化

- Python 最低版本固定为 3.11；Windows 与 Ubuntu CI 同时覆盖 Python 3.11 和 3.13，安装器与完整验证在旧解释器上失败关闭。
- 完整验证加入 Git index、受管与未跟踪内容摘要、删除状态、链接类型和中断路径的工作区前后快照；输出文件必须位于仓库外。
- 受控演进改为按信号类型检查证据：模型升级需要实际模型覆盖，负面结果需要终态覆盖，其他信号不再被无关遥测缺失阻断；覆盖率按唯一 `task_id` 计算。
- 新增 11 个真实 Codex 宿主路由场景。验收报告验证 Plugin 安装/启用读回、全新独立任务、无显式 Skill 名称、最终报告字节数与 SHA-256，并明确不等同于宿主签名的内部路由 Trace。
- 安装器兼容 Codex CLI 0.152.1 的严格本地 Marketplace schema，升级时移除已知不兼容的顶层 `owner/interface` 字段，同时保留未知外部元数据。
- `long-running-task-memory` 与 `multi-agent-independent-review` 不再复制受控演进规范，统一路由到 `controlled-evolution-governance` 作为唯一权威入口。

## 不变安全边界

- `execution_authorization=NONE`
- 未验证 Codex CLI 版本的 Plugin 安装继续失败关闭
- Skill 激活不扩大文件、Git、环境、生产或数据权限
- 自动子 Agent 模型上限保持 `gpt-5.6-terra + high`

## 验收边界

包级路由回归只证明静态用例与工具契约，状态固定为 `routing_host_observation=NOT_EVALUATED`；真实宿主验收、完整本机安装、远端发布与下载后制品核对分别记录，任一阶段的 PASS 不替代其他阶段的动作读回。
