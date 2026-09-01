# V7.0.0 发行说明

English: [RELEASE_NOTES.en.md](RELEASE_NOTES.en.md)

版本：7.0.0

## 核心变化

- 新增语言中立的 `$backend-engineering`，覆盖 Node.js、Go、.NET、Rust 及混合语言后端，并按需加载 Java、Python 专项规则。
- 新增独立的 `$ai-engineering`，覆盖模型接入、结构化输出、RAG、Agent、评测、推理与多模态。
- `$frontend-engineering` 保持独立；`$data-middleware-infrastructure` 聚焦数据库、中间件、存储、GPU 资源、容器和网络运行边界。
- 旧的 Java、Python+AI、Data+AI 三个 Skill 名称不再作为可路由 Skill；安装器仅清理 Manifest 声明的四个旧目录，其中还包括此前已废弃的 Vue Skill。
- 中英文职责矩阵、正反路由用例、Manifest、AGENTS、安装恢复与发行脚本同步升级到 7.0.0。
- 新增中英文独立文档站、全仓库 Markdown 链接审计、版本化发行证据、双语可复现制品和仅创建草稿的 GitHub Release 来源证明工作流。

## 不变安全边界

- `execution_authorization=NONE`
- Skill 激活不扩大文件、Git、环境、生产或数据权限
- 不自动提交、推送、发布、部署、重启或执行生产写入
- 自动子 Agent 模型上限保持 `gpt-5.6-terra + high`

## 验收边界

包内验证与[真实 Codex 隐式触发观察](IMPLICIT_TRIGGER_OBSERVATION.md)分别记录；四个代表性隐式路由场景、源码树 `6.6.0 -> 7.0.0` Plugin 升级和全新任务路由均 PASS。公开 Release ZIP 仍需独立来源证明和下载后验收；该结果不等于所有提示词变体都能确定性命中。
