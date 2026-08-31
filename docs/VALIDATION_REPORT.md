# v2.0 安装包验证报告

## 验证范围

- 7 个 Skill 的目录、`SKILL.md`、YAML Frontmatter 和 `agents/openai.yaml`；
- `manifest.json` 与实际目录一致性；
- 全局 `AGENTS.md` 受管标记、Markdown 结构和文件大小；
- 12 个技术文档模板；
- Markdown 代码块闭合；
- 用户级安装、重复安装、验证和卸载；
- 仓库级安装和卸载；
- 现有 `AGENTS.md` 非本包内容保留；
- 重复安装后受管区块不重复。

## 已执行验证

| 验证项 | 环境 | 结果 |
|---|---|---|
| `validate-package.py` | Linux 容器 / Python 3 | 通过 |
| `install-user.sh` 首次安装 | 临时 HOME | 通过 |
| `verify-user-install.sh` | 临时 HOME | 通过 |
| `install-user.sh` 重复安装 | 临时 HOME | 通过，受管区块保持单份 |
| 原有 `AGENTS.md` 内容保留 | 临时 HOME | 通过 |
| `install-repo-skills.sh` | 临时仓库 | 通过 |
| `uninstall-repo-skills.sh` | 临时仓库 | 通过 |
| `uninstall-user.sh` | 临时 HOME | 通过，仅移除本包内容 |
| PowerShell 脚本 | 静态结构检查 | 当前生成环境无 PowerShell，未执行 Windows 实机验证 |

## 结论

Linux / WSL 路径下的安装、升级、验证和卸载流程已完成实际验证。Windows PowerShell 脚本与 Shell 脚本保持同等逻辑，但仍建议用户首次安装后运行 `verify-user-install.ps1` 进行本机验证。
