# V7.1.0 包内与本机安装验证报告

English: [VALIDATION_REPORT.en.md](VALIDATION_REPORT.en.md)

版本：7.1.0

验证日期：2026-09-02

## 当前状态

包内验证与本机完整安装均已通过：

- package 测试 129 项、runtime 测试 6 项、Skill 路由 45 项全部通过；语义检查、严格本地化检查、Markdown 链接检查和 payload manifest 检查通过。
- 中文和英文发行包分别完成两次全新构建，同语言归档逐字节一致。
- 本机 Codex CLI `0.152.1` 完成账户级 Plugin 从 `7.0.0` 升级到 `7.1.0`，`install` 与 `verify` 均返回成功，升级事务已清空。
- `codex plugin list --json` 精确读回目标 Plugin `installed=true`、`enabled=true`、`version=7.1.0`。
- 源码、Marketplace 与 Plugin cache 均为 182 个受管 payload 文件，摘要一致：`b9b4fa3d957dd4b58094c7aac50fac38ec484405ce28369583d094609750db4d`。
- 账户级 `cp-runtime.py` 与 `evolution.py` 均可启动并完整显示命令入口；安装文件 SHA-256 与仓库源文件分别一致，修复了旧安装中共享 `cp_runtime.evolution` 模块不可用的问题。
- 账户状态记录 `codex-cli 0.152.1` 能力探测通过，无活动事务；六类 Hook、受管规则、10 个 Skill 与 7 个 Reviewer 通过安装校验。

## 固定验收门禁

- Manifest、Plugin、payload 与发行脚本版本一致
- 定向测试、package 全量测试和 runtime 全量测试通过
- 中文、英文发行包两次构建字节一致
- 本机 `install --scope user --mode plugin` 与 `verify` 通过
- `codex plugin list --json` 精确读回 `installed=true`、`enabled=true`、`version=7.1.0`
- 账户级 `cp-runtime.py`、`evolution.py` 可运行，六类 Hook 与受管全局规则加载一致

截至本报告形成时，提交、推送、标签、GitHub Release 与公开制品尚未执行；这些状态必须在各自动作后单独读回。
