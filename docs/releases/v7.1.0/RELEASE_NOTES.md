# V7.1.0 发行说明

English: [RELEASE_NOTES.en.md](RELEASE_NOTES.en.md)

版本：7.1.0

## 核心变化

- 当前 Codex CLI 兼容基线升级到 0.152.1；安装器保留 0.150.1 的已验证兼容，并对其他未验证版本继续失败关闭。
- Plugin Marketplace 的 add/remove/list 命令与 `plugin list --json` 核心字段已在 Windows 原生 Codex CLI 0.152.1 实机核对。
- Plugin 与 standalone 安装现在都事务化安装、校验和卸载账户级 `cp-runtime.py`、`evolution.py` 工具。
- 账户 runtime 在受限任务中不可读时，启动器按安装状态精确回退到当前 Plugin cache，不跨版本猜测路径。
- Manifest、Plugin 元数据、双语构建、发行验证、证明与当前操作文档统一升级到 7.1.0，并加入 7.0.0 升级路径。

## 不变安全边界

- `execution_authorization=NONE`
- 未验证 Codex CLI 版本的 Plugin 安装继续失败关闭
- Skill 激活不扩大文件、Git、环境、生产或数据权限
- 自动子 Agent 模型上限保持 `gpt-5.6-terra + high`

## 验收边界

包内验证、本机 0.152.1 完整 Plugin 安装、远端发布与下载后制品核对分别记录；任一阶段的 PASS 不替代其他阶段的动作读回。
