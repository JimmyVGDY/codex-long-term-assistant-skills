# Codex 跨项目长期技术助手 V6.6.1

English: [README.en.md](README.en.md)

目标宿主：Windows 原生 Codex CLI 0.150.1。Plugin 成功状态仅以 `codex plugin list --json` 读回 `installed=true`、`enabled=true`、`version=6.6.1` 为准。

V6.6.1 提供两个完整、可独立安装、可复现构建的发行包：

- `Codex-Skills-V6.6.1-zh-CN.zip`
- `Codex-Skills-V6.6.1-en.zip`

两个发行包共享 Runtime、Hooks、安装器、Schema、测试和安全策略。英文发行覆盖 README、全局规则、10 个 Skill 入口、7 个 Reviewer、安装配置、使用说明和发行说明；历史证据与底层测试夹具按原始形态保留。

## 能力范围

- 10 个工程 Skill，按任务上下文渐进加载。
- 7 个逻辑只读 Reviewer，TOML 不写死模型与推理强度。
- 6 个生命周期 Hook：`UserPromptSubmit`、`PreToolUse`、`SubagentStart`、`SubagentStop`、`Stop`、`SessionEnd`。
- TaskOutcomeEvent 2.0、`project_id + repo_fingerprint` 双重隔离和连续哈希链。
- SessionEnd 三秒预算外的延迟封印。
- 非破坏事件归档、容量报告和隐私有界的跨项目健康概览。
- `execution_authorization=NONE` 的受控优化提案。

## 模型证据口径

```ini
requested_model_policy = PASS
runtime_model_evidence = UNAVAILABLE
diagnostic_model_observation = 仅诊断旁证
```

Codex 0.150.1 尚未向 Hook 提供可信且可关联的实际模型证明。请求 Luna 或 Terra 配置，不等于实际运行模型已验证。自动派发只允许：

```text
luna-low -> luna-medium -> terra-medium -> terra-high
```

自动上限为 `gpt-5.6-terra + high`；Sol、`xhigh`、`max`、`ultra` 均拒绝。

## 升级安装

在解压后的语言包根目录执行：

```powershell
python scripts\package_manager.py doctor
python scripts\package_manager.py install --scope user --mode plugin --dry-run
python scripts\package_manager.py install --scope user --mode plugin
python scripts\package_manager.py verify --scope user --mode plugin
codex plugin list --json
```

dry-run 需证明备份范围有界、路径未越界、链接与 Reparse Point 风险被拒绝、未知文件被保留、回滚链完整。仅复制文件不构成 Plugin 安装成功。

详细入口：`docs/USER_GUIDE_V6.6.1.md`、`docs/INSTALLATION_RECOVERY.md`、`docs/CODEX_CONFIG_GUIDE.md`。对应英文文档使用同名 `.en.md` 文件。

## 发行构建

```powershell
python scripts\build-release.py reproducible --locale zh-CN --output Codex-Skills-V6.6.1-zh-CN.zip --witness deterministic-build-v6.6.1-zh-CN.json
python scripts\build-release.py reproducible --locale en --output Codex-Skills-V6.6.1-en.zip --witness deterministic-build-v6.6.1-en.json
```

## 安全边界

- 不自动修改 Skill、Reviewer、模型路由、全局配置或业务仓库。
- 不自动接受或执行优化提案。
- 不自动提交、推送、部署、重启、操作生产环境或写入业务数据。
- Evidence 只记录事实，不授予权限。

许可证：Apache-2.0，见 `LICENSE`。
