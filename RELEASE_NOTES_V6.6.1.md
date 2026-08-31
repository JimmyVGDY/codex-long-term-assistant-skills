# V6.6.1 发行说明

版本：6.6.1

## 已实现

- 新增 `zh-CN` 与 `en` 两个可复现、可独立安装的完整发行包。
- 英文发行覆盖 README、全局规则、10 个 Skill 入口、7 个 Reviewer、安装配置、使用说明和发行说明。
- Windows 原子文件发布对短暂共享冲突实施有界重试。
- 新增仅用于验证的封印进程显式等待；生产 SessionEnd 仍为异步，不占用三秒预算。
- Plugin 成功判定保持 `installed=true`、`enabled=true`、`version=6.6.1` 三项精确读回。

## 不变安全边界

- `execution_authorization=NONE`
- 不自动修改 Skill、Reviewer 或模型路由
- 不自动接受或执行 Proposal
- 不自动提交、推送、部署、重启、生产操作或数据写入
- Reviewer TOML 不写死模型
- 自动模型上限为 `gpt-5.6-terra + high`

## 模型证据

Codex 0.150.1 仍只能提供诊断旁证：

```ini
requested_model_policy = PASS
runtime_model_evidence = UNAVAILABLE
diagnostic_model_observation = 仅诊断旁证
```
