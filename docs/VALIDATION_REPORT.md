# v3.0 安装包验证报告

## 一、验证信息

- 安装包版本：`3.0.0`
- 版本名称：持续记忆与多 Agent 复审版
- 验证时间：2026-07-29 15:43:54 Asia/Shanghai
- 验证环境：Linux x86_64 容器
- Python：3.13.5
- Git：2.47.3
- 主校验命令：

```bash
python3 scripts/validate-package.py
```

## 二、验证范围

本次校验覆盖：

- `manifest.json` 版本、Skill、Reviewer 和质量上限；
- 全局 `AGENTS.md` 受管标记、关键规则、Markdown 结构和文件大小；
- 8 个 Skill 的目录、`SKILL.md`、YAML Frontmatter、描述和相对引用；
- 8 个 `agents/openai.yaml` 的界面字段和隐式调用策略；
- 7 个自定义 Reviewer TOML 的名称、描述、开发指令和只读沙箱；
- 多 Agent 并发配置示例；
- 12 个正式技术文档模板；
- 10 个外部记忆与恢复模板；
- 3 个多 Agent 复审模板；
- Markdown 代码块和硬编码个人路径；
- Shell 安装、验证和卸载脚本语法；
- PowerShell 脚本静态结构；
- `checkpoint.py` 的初始化、追加、校验、恢复、修复和归档；
- Git 指纹漂移检测；
- 用户级首次安装、重复升级、验证和卸载；
- 仓库级 Skills 与 Reviewer 安装和卸载；
- 对用户原有 `AGENTS.md`、第三方 Skills 和其他自定义 Agent 的保留。

## 三、结构与内容校验

| 校验项 | 实际结果 |
|---|---|
| Manifest | 版本 `3.0.0`，8 个 Skills，7 个 Reviewer，结构一致 |
| 全局 `AGENTS.md` | 20,274 bytes，低于包内 24 KiB 校验上限 |
| Skills | 8 个全部通过 |
| 自定义 Reviewer | 7 个全部通过，均为 `read-only` |
| Agent 配置示例 | TOML 解析通过，并发上限为 6 |
| 正式文档模板 | 12 个齐全 |
| 外部记忆模板 | 10 个齐全 |
| 复审模板 | 3 个齐全 |
| Markdown | 代码块闭合检查通过 |
| 路径检查 | 未发现本包禁止的硬编码个人路径 |

通过的 Skills：

```text
data-middleware-ai-infrastructure
engineering-quality-delivery
java-backend-engineering
long-running-task-memory
multi-agent-independent-review
python-backend-ai-engineering
technical-document-writing
vue-frontend-engineering
```

通过的只读 Reviewer：

```text
cp_review_compatibility_regression
cp_review_data_contract
cp_review_functional_business
cp_review_performance_resources
cp_review_security_access
cp_review_state_concurrency
cp_review_test_delivery
```

## 四、检查点工具实际验证

`skills/long-running-task-memory/scripts/checkpoint.py` 已在临时 Git 仓库和仓库外记忆目录中完成实际运行验证。

| 命令 | 验证内容 | 结果 |
|---|---|---|
| `init` | 初始化任务、计划、进度、复审和归档结构 | 通过 |
| `append` | 追加检查点并刷新当前任务快照 | 通过 |
| `validate` | 检查检查点 ID、状态版本和文档一致性 | 通过 |
| `recover` | 输出当前快照和最近检查点 | 通过 |
| `repair` | 模拟快照状态不一致后按最后检查点修复 | 通过 |
| `archive` | 将超出热区限制的检查点归档并保留索引 | 通过 |
| Git 指纹 | 修改测试仓库后使用严格模式识别状态漂移 | 通过 |
| 锁与原子写入路径 | 由脚本逻辑及完整工作流自测覆盖 | 通过 |

自测还确认：

- 默认拒绝把外部任务记忆写入 Git 工作区；
- `PROGRESS.md` 与 `CURRENT_TASK.md` 的最后检查点保持一致；
- 当前快照损坏或未刷新时可以从最后检查点恢复；
- 归档后活跃进度仍可继续追加和验证。

## 五、安装、升级与卸载验证

### 5.1 用户级 Shell 流程

在隔离临时 `HOME` 和 `CODEX_HOME` 中实际执行：

1. 首次安装；
2. 安装后验证；
3. 重复安装模拟原地升级；
4. 检查全局受管区块没有重复；
5. 检查用户原有 `AGENTS.md` 非受管内容仍保留；
6. 检查第三方 Skill 和其他自定义 Agent 仍保留；
7. 卸载本包；
8. 检查仅移除本包受管内容。

结果：**全部通过**。

### 5.2 仓库级 Shell 流程

在隔离临时 Git 仓库中实际执行：

1. 安装仓库级 8 个 Skills；
2. 使用选项安装 7 个仓库级 Reviewer；
3. 检查第三方仓库资源保留；
4. 卸载本包 Skills 和 Reviewer；
5. 检查仅移除本包内容。

结果：**全部通过**。

## 六、脚本校验

### 6.1 Shell

以下脚本均通过 `bash -n`：

```text
install-repo-skills.sh
install-user.sh
uninstall-repo-skills.sh
uninstall-user.sh
verify-user-install.sh
```

### 6.2 PowerShell

以下脚本已完成静态结构检查：

```text
install-repo-skills.ps1
install-user.ps1
uninstall-repo-skills.ps1
uninstall-user.ps1
verify-user-install.ps1
```

当前生成环境没有 `pwsh` 或 Windows PowerShell，因此：

- 未运行 PowerShell 官方解析器；
- 未执行 Windows 原生用户目录安装；
- 未执行 Windows 原生升级和卸载。

这部分状态为：**静态检查通过，Windows 实机未验证**。

用户在 Windows 安装后应执行：

```powershell
powershell -ExecutionPolicy Bypass -File ".\scripts\verify-user-install.ps1"
```

## 七、验证命令最终输出摘要

```text
[OK] manifest.json: version 3.0.0，8 Skills，7 Reviewer
[OK] 全局 AGENTS.md: 20274 bytes
[OK] 8 个 Skill
[OK] 7 个只读 Reviewer
[OK] 12 个正式文档模板
[OK] 10 个外部记忆模板
[OK] 3 个复审模板
[OK] Markdown 代码块与个人路径检查
[OK] Shell 脚本语法
[OK] PowerShell 静态结构
[OK] checkpoint.py: init / append / validate / recover / repair / archive
[OK] Shell 用户级首次安装 / 重复升级 / 验证 / 卸载
[OK] Shell 仓库级 Skills + Reviewer 安装 / 卸载
[WARN] 当前环境没有 PowerShell；未执行 Windows PowerShell 解析器和实机安装
验证通过
```

## 八、最终结论

**v3.0 包结构、Skill 内容、只读 Reviewer、持续检查点工具、Shell 安装升级流程和仓库级安装卸载流程已通过实际验证。**

当前唯一环境限制是未在 Windows PowerShell 中执行实机验证。因此不能将 PowerShell 状态表述为已经在 Windows 运行通过；Windows 用户应在本机安装后运行验证脚本，并以本机输出为准。
