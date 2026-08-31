# Codex 跨项目长期技术助手 Skills 安装包

本安装包已转换为 Codex 原生结构：

- 全局硬规则：安装到 `~/.codex/AGENTS.md`；
- 用户级 Skills：安装到 `$HOME/.agents/skills/<skill-name>/`；
- 每个 Skill 均包含带 YAML 元数据的 `SKILL.md`；
- 详细工程规则位于 `references/`，模板位于长期任务 Skill 的 `assets/templates/`；
- `agents/openai.yaml` 提供显示名称、说明、默认提示和隐式调用策略。

## 包含的 Skills

| Skill | 主要触发场景 |
|---|---|
| `$java-backend-engineering` | Java、Spring、MyBatis、事务、并发、JVM、SSE |
| `$python-backend-ai-engineering` | Python Web、异步、Celery、AI、RAG、GPU Worker |
| `$vue-frontend-engineering` | Vue、路由、状态、异步竞态、SSE、构建 |
| `$data-middleware-ai-infrastructure` | 数据库、Redis、MQ、搜索、文件、AI、Docker、K8s |
| `$engineering-quality-delivery` | 修改、测试、六维复审、Git、部署、生产安全 |
| `$long-running-task-memory` | 跨会话计划、进度、决策、交接和交付记录 |

## Windows 一键安装

在 PowerShell 中进入解压后的安装包目录，执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install-user.ps1
```

默认行为：

1. 使用 `$env:CODEX_HOME`，未设置时使用 `$HOME\.codex`；
2. 备份已有全局 `AGENTS.md` 和本包同名 Skills；
3. 安装全局规则与全部 Skills；
4. 不删除或覆盖其他第三方 Skills。

仅安装 Skills：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install-user.ps1 -Component SkillsOnly
```

仅安装全局规则：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install-user.ps1 -Component GlobalOnly
```

验证：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify-user-install.ps1
```

## WSL / Linux 一键安装

```bash
chmod +x scripts/*.sh
./scripts/install-user.sh
./scripts/verify-user-install.sh
```

仅安装 Skills：

```bash
./scripts/install-user.sh skills
```

仅安装全局规则：

```bash
./scripts/install-user.sh global
```

> Windows Codex 与 WSL 内运行的 Codex 使用不同的 `$HOME`。在哪个环境运行 Codex，就在对应环境执行安装脚本。

## 安装到单个仓库

用户级安装适合跨项目长期使用。某个仓库需要独立携带 Skills 时，可执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install-repo-skills.ps1 -RepoPath D:\projects\your-repo
```

```bash
./scripts/install-repo-skills.sh /path/to/your-repo
```

该脚本只复制 Skills 到 `<repo>/.agents/skills`，不会把全局 `AGENTS.md` 写入仓库。

## 使用

Codex 可以根据 Skill 的 `description` 自动匹配，也可以显式调用：

```text
使用 $java-backend-engineering 和 $engineering-quality-delivery，
审查并修复当前 Spring Boot 接口，执行相关定向测试，本地提交但不要推送。
```

```text
使用 $python-backend-ai-engineering、$data-middleware-ai-infrastructure
和 $engineering-quality-delivery，排查 Celery GPU 任务阻塞问题，只分析，不修改。
```

在 Codex CLI 或 IDE 中使用 `/skills` 查看已发现的技能。新技能通常会自动被检测；未出现时重启 Codex。

## 安全说明

- 安装脚本只操作当前用户目录或显式指定的仓库；
- 已存在文件会备份到 `$HOME/.codex-skill-backups/<timestamp>/`；
- 不修改 `config.toml`，不禁用其他 Skills；
- 不执行 Git、部署、数据库或生产环境操作。
