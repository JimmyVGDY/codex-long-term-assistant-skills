# Codex 跨项目长期技术助手 V6.6 使用说明

## 1. 日常工程任务

直接描述任务即可。Skill 根据技术栈和阶段渐进加载；普通任务不会自动触发完整 Evolution。修改、测试、提交、推送、部署和重启仍是独立授权边界。

## 2. 安装与确认

```powershell
python scripts\package_manager.py doctor
python scripts\package_manager.py install --scope user --mode plugin --dry-run
python scripts\package_manager.py install --scope user --mode plugin
python scripts\package_manager.py verify --scope user --mode plugin
codex plugin list --json
```

成功状态必须同时满足 `installed=true`、`enabled=true`、`version=6.6.0`。

## 3. 模型门禁与证据

```powershell
python scripts\model-gate-acceptance.py --output model-gate-v6.6.json
```

自动路线为 Luna Low → Luna Medium → Terra Medium → Terra High。显式 Terra xhigh、Sol、max 和 ultra 均被拒绝。

输出分为：

```ini
requested_model_policy = PASS
runtime_model_evidence = UNAVAILABLE
diagnostic_model_observation = gpt-5.6-luna / low
```

Codex 0.150.1 的 rollout 只提供诊断旁证。只有未来宿主向 Hook 提供可信证明且通过关联、时效和签名校验，`runtime_model_evidence` 才可变为 VERIFIED。

## 4. 延迟自动封印

SessionEnd 只写签名 job 并启动 detached worker。worker 后续追加 `SESSION_ENDED`、验证完整链并形成 detached seal。手动排空方式：

```powershell
python scripts\seal-worker.py --queue <project-context>\<project-id>\feedback\seal-queue
```

队列具有 pending、running、done、dead-letter 四个目录。worker 被终止后，后续进程会重领已退出进程的 running job；event_id 和 seal 均保持幂等。

## 5. 归档、容量和健康概览

```powershell
python scripts\event-archive.py archive --event-file <task-outcome-v2.jsonl>
python scripts\event-archive.py verify --event-file <task-outcome-v2.jsonl>
python scripts\event-archive.py capacity --project-dir <project-context>\<project-id>
python scripts\event-archive.py health --project-context-root <project-context>
```

归档只复制已关闭 segment，不移动活动文件，不删除 Event、Snapshot、Assessment 或 Proposal。容量达到阈值时只报告或阻止自动扩张，不自动清理历史。

## 6. Reviewer 校准

校准结果包含任务难度分布、稳定根因簇、重复簇比例、采纳原因、回归预防 claim 与证据覆盖率。缺少任务难度、采纳原因或回归测试引用时明确计入 UNKNOWN/UNSPECIFIED/insufficient-evidence，不推断收益。

## 7. 安全边界

- 不改写主 Agent 模型。
- Reviewer TOML 不固定模型。
- 自动流程最高 Terra High。
- 不自动接受或实施 Proposal。
- 不自动提交、推送、部署、重启或操作生产环境。
- 不记录原始 Prompt、完整回答、代码正文、Diff、Token、Cookie、API Key 或凭据。

