# Codex 跨项目长期技术助手 Skills 安装包 v2.0

本包用于把跨项目工程规则安装为 Codex 原生用户级或仓库级 Skills，并提供可保留现有规则的全局 `AGENTS.md` 安装方式。

## v2.0 主要变化

- 新增 `$technical-document-writing`：负责技术方案、架构设计、实施计划、接口与数据库设计、部署手册、故障报告、代码审查报告、项目报告、README 和 Markdown 重构；
- 新增 12 个正式技术文档模板；
- 全局 `AGENTS.md` 改为受管区块合并，默认保留用户原有全局规则；
- 新增用户级和仓库级卸载脚本；
- 验证脚本增加 Skill 元数据、`openai.yaml`、受管区块和文档模板检查；
- 新增跨平台包结构校验脚本；
- 明确正式工程文档、CHANGELOG 和 Agent 外部记忆三者的职责边界。

## 原生目录结构

- 全局规则：`${CODEX_HOME:-$HOME/.codex}/AGENTS.md`；
- 用户级 Skills：`$HOME/.agents/skills/<skill-name>/`；
- 仓库级 Skills：`<repo>/.agents/skills/<skill-name>/`；
- 每个 Skill 都包含 `SKILL.md` 和 `agents/openai.yaml`；
- 详细规则位于 `references/`，模板位于 `assets/templates/`。

## 包含的 Skills

| Skill | 主要触发场景 |
|---|---|
| `$java-backend-engineering` | Java、Spring、MyBatis、事务、并发、JVM、SSE |
| `$python-backend-ai-engineering` | Python Web、异步、Celery、AI、RAG、GPU Worker |
| `$vue-frontend-engineering` | Vue、路由、状态、请求竞态、SSE、构建 |
| `$data-middleware-ai-infrastructure` | 数据库、Redis、MQ、搜索、文件、AI、Docker、K8s |
| `$engineering-quality-delivery` | 修改、测试、六维复审、Git、部署、生产安全 |
| `$technical-document-writing` | 技术方案、架构文档、正式报告、设计说明和文档重构 |
| `$long-running-task-memory` | 跨会话计划、进度、决策、交接和交付记录 |

## 文档 Skill 包含的模板

- 技术方案；
- 架构设计；
- 实施计划；
- API 设计；
- 数据库设计；
- 部署与回滚手册；
- 故障分析与复盘；
- 代码审查报告；
- 项目进度与交付报告；
- 技术选型评估；
- README；
- 面向管理层的正式报告。

模板只是起点。Skill 会根据任务裁剪，不会机械生成全部章节。

---

## Windows 用户级安装

### 1. 解压并进入安装包根目录

确认当前目录能看到：

```text
README.md
global
skills
scripts
```

### 2. 安装全局规则和全部 Skills

```powershell
powershell -ExecutionPolicy Bypass -File ".\scripts\install-user.ps1"
```

默认行为：

1. 使用 `$env:CODEX_HOME`，未设置时使用 `$HOME\.codex`；
2. 备份现有 `AGENTS.md` 和本包同名 Skills；
3. 如果 `AGENTS.md` 已存在，只新增或更新本包的受管区块，保留其他规则；
4. 覆盖本包同名 Skill，但不删除其他第三方 Skills；
5. 不修改 `config.toml`，不执行 Git、部署或生产操作。

只安装 Skills：

```powershell
powershell -ExecutionPolicy Bypass -File ".\scripts\install-user.ps1" -Component SkillsOnly
```

只安装全局规则：

```powershell
powershell -ExecutionPolicy Bypass -File ".\scripts\install-user.ps1" -Component GlobalOnly
```

明确要求完整替换现有全局 `AGENTS.md` 时：

```powershell
powershell -ExecutionPolicy Bypass -File ".\scripts\install-user.ps1" -Component GlobalOnly -ForceReplaceGlobal
```

> `-ForceReplaceGlobal` 会整体替换目标文件。正常升级不需要使用。

### 3. 验证

```powershell
powershell -ExecutionPolicy Bypass -File ".\scripts\verify-user-install.ps1"
```

### 4. 卸载本包

```powershell
powershell -ExecutionPolicy Bypass -File ".\scripts\uninstall-user.ps1"
```

卸载只删除本包管理的 7 个 Skills 和 `AGENTS.md` 中的本包受管区块，不删除其他规则或 Skills。

---

## WSL / Linux 用户级安装

```bash
chmod +x scripts/*.sh scripts/validate-package.py
./scripts/install-user.sh
./scripts/verify-user-install.sh
```

只安装 Skills：

```bash
./scripts/install-user.sh skills
```

只安装全局规则：

```bash
./scripts/install-user.sh global
```

完整替换全局规则：

```bash
./scripts/install-user.sh global --force-replace-global
```

卸载：

```bash
./scripts/uninstall-user.sh
```

> Windows 原生 Codex 与 WSL 中运行的 Codex 使用不同的 `$HOME`。在哪个环境运行 Codex，就在对应环境执行一次安装。

---

## 安装到单个仓库

Windows：

```powershell
powershell -ExecutionPolicy Bypass -File ".\scripts\install-repo-skills.ps1" -RepoPath "D:\projects\your-repo"
```

WSL / Linux：

```bash
./scripts/install-repo-skills.sh /path/to/your-repo
```

仓库级卸载：

```powershell
powershell -ExecutionPolicy Bypass -File ".\scripts\uninstall-repo-skills.ps1" -RepoPath "D:\projects\your-repo"
```

```bash
./scripts/uninstall-repo-skills.sh /path/to/your-repo
```

仓库级安装只操作 `<repo>/.agents/skills`，是否提交到 Git 由项目规范决定。

---

## 使用示例

### 自动匹配文档 Skill

直接描述任务即可：

```text
根据当前项目代码、配置和现有文档，编写一份正式的系统架构设计文档。
必须区分已确认事实、推断和未验证项，并给出部署、监控、风险和演进路线。
```

### 显式调用文档 Skill

```text
使用 $technical-document-writing、$java-backend-engineering
和 $data-middleware-ai-infrastructure。

基于当前仓库实际代码，编写订单模块重构技术方案，
保留现有业务口径，提供候选方案对比、推荐方案、实施步骤、
兼容性、性能、安全、灰度、回滚和验收标准。
```

### 修改代码并同步正式文档

```text
使用 $java-backend-engineering、$engineering-quality-delivery
和 $technical-document-writing。

修复当前接口问题，执行相关后端定向测试和六维复审，
同步更新项目已有技术文档和 CHANGELOG，创建本地提交但不要推送。
```

### 长期任务中的文档边界

```text
使用 $long-running-task-memory 维护 Codex 外部任务计划和进度；
使用 $technical-document-writing 编写团队正式实施方案。
外部记忆文件不得进入项目仓库。
```

在 Codex CLI 或 IDE 中使用 `/skills` 查看已发现技能，也可以输入 `$` 显式选择 Skill。

---

## 包结构校验

安装前可执行：

```powershell
python .\scripts\validate-package.py
```

```bash
python3 ./scripts/validate-package.py
```

校验内容包括：

- `manifest.json` 与实际 Skills 一致；
- 每个 `SKILL.md` 的 `name`、`description` 和引用路径；
- `agents/openai.yaml`；
- 全局 `AGENTS.md` 受管区块和大小；
- 12 个技术文档模板；
- Markdown 代码块闭合；
- 安装、验证和卸载脚本齐全。

## 安全说明

- 安装和卸载前默认备份到 `$HOME/.codex-skill-backups/<timestamp>/`；
- 默认合并全局受管区块，不覆盖其他个人或公司规则；
- 只操作当前用户目录或显式指定仓库；
- 不修改 Codex 权限、MCP、网络、Git、数据库和生产环境；
- 文档 Skill 不会因被激活而获得代码、Git 或环境写权限。
