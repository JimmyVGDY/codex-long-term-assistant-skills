# V6 安装、验证与恢复

## 账户级目录

- Skill：`$HOME/.agents/skills`
- Reviewer：`${CODEX_HOME:-$HOME/.codex}/agents`
- Global：`${CODEX_HOME:-$HOME/.codex}/AGENTS.md`
- Standalone Hook：`${CODEX_HOME:-$HOME/.codex}/hooks.json` + `cp-assistant-hooks/cp_hook.py`

## 安全流程

安装前使用 `--dry-run`。安装器拒绝链接型父目录、源码目录自覆盖和 Repo 越界路径；覆盖受管目标前创建备份。卸载依据安装状态和内容 Hash 检测外部漂移，默认不删除未知资产。

## 恢复原则

V6 卸载会按安装事务备份恢复安装前资源。项目上下文、Event、Snapshot、Proposal 等历史治理数据不随卸载自动删除，避免破坏审计链。
