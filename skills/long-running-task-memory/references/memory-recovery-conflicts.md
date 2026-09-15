# 恢复协议与状态冲突处理

## 十一、固定恢复协议

上下文压缩、会话恢复、模型切换、主 Agent 切换或长时间暂停后，不得直接继续修改。

按顺序执行：

已有增强 runtime 且请求方提供了明确的 Profile、检查点与 Evidence 路径时，先调用一次已安装 `cp-runtime.py project-resume --repo-path <仓库> --profile <Profile> --checkpoint-dir <检查点目录> --evidence <Evidence> --json`，复用其中的身份、基线与过期证据结果，避免逐文件重复查询。多个 Evidence 重复传参。没有增强 runtime 时沿用下方手动流程或 Skill 自带的 `checkpoint.py recover`；不为恢复查询自动安装、初始化或修复状态。摘要不是授权，PARTIAL/UNKNOWN/STALE 必须保持原意，再阅读下一步涉及的源码。

1. 读取当前请求和当前授权；
2. 读取平台、全局和项目级 `AGENTS.md`；
3. 读取 `PROJECT_CONTEXT.md`；
4. 读取 `CURRENT_TASK.md`；
5. 读取 `PLAN.md` 当前阶段；
6. 读取 `PROGRESS.md` 最近 3 个检查点；
7. 按引用读取相关 `DECISIONS.md` 和 Reviewer 报告；
8. 必要时读取 `HANDOFF.md`；
9. 执行 `git status`；
10. 确认分支、HEAD、基线和未跟踪文件；
11. 检查 `git diff`、`git diff --stat` 和最近提交；
12. 对比文档状态与实际仓库状态；
13. 重新阅读“下一步唯一行动”涉及的核心代码、配置和测试；
14. 无冲突后才继续执行。

```text
RECENT_CHECKPOINTS_TO_LOAD = 3
```

不得只根据 `HANDOFF.md`、自动摘要、Codex Memories 或历史聊天结论直接修改代码。

---

## 十二、状态冲突处理

以下情况必须先停止和对账：

- 当前分支与文档不一致；
- HEAD Commit 不一致；
- Git diff 超出记录范围；
- 文件被其他 Agent 或外部修改；
- 文档写“测试通过”，但代码随后又变化；
- 计划中的下一步已被其他人完成；
- 授权边界、环境或数据目标不明确；
- 文档与运行状态冲突。

处理步骤：

1. 记录“状态分歧检查点”；
2. 明确冲突内容；
3. 以实际代码、配置、Git 和运行结果为准；
4. 重新验证受影响结论；
5. 修正文档；
6. 重新确定下一步。

旧测试结果在相关代码变化后自动失效，必须标记为“需重新验证”。

---
