# Codex V5.0 安装、诊断和恢复

- `install-user.* --dry-run`：仅显示计划；
- `verify-user-install.*`：验证受管区块、9 个 Skills、Reviewer 和废弃目录；
- `doctor.*`：报告实际 Home、Skills、Agents、重复路径和依赖；
- `restore-latest-backup.*`：根据备份 manifest 恢复安装前状态；
- `uninstall-user.*`：只删除本包受管资源，保留第三方内容。

Codex V5.0 使用 `${CODEX_HOME:-$HOME/.codex}/skills`，并检测旧 `$HOME/.agents/skills` 同名副本。

## V5.0 配置提醒

安装脚本不会自动修改 `${CODEX_HOME:-$HOME/.codex}/config.toml`。安装完成后按 `CODEX_CONFIG_GUIDE.md` 合并 `[agents]`，并重启当前 Codex 客户端。Reviewer TOML 不应写死模型或推理强度。
