# 前端 Skill v4.0 迁移说明（Codex）

原 Skill `vue-frontend-engineering` 已直接改名为 `frontend-engineering`，不保留兼容别名。

- 旧调用：`$vue-frontend-engineering`
- 新调用：`$frontend-engineering`

升级脚本会备份旧目录后移除，再安装新 Skill；其他第三方 Skill 不受影响。升级后重启 Codex 并运行 `/skills`，确认只出现 `frontend-engineering`，不再出现旧名称。
