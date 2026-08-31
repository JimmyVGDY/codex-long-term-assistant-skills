# 研发质量、验证、生产与 Git 交付工作流

> V5.0 继续按需加载，并增加项目身份绑定、Approval/Evidence 分离与最终状态读回。先读取本索引，只加载当前任务需要的分片。

## 加载索引

| Reference | 内容 | 何时读取 |
|---|---|---|
| `quality-task-planning.md` | 任务分类、修改前计划与实施前门禁 | 任务开始、范围确认、实施计划或高风险设计审查 |
| `execution-profiles-and-phases.md` | `LIGHT/STANDARD/STRICT` 与执行阶段 | 选择执行门禁和阶段转换 |
| `task-execution-envelope.md` | Task Envelope V2、Project Binding 与六维路由 | 非简单、跨会话或受保护操作任务 |
| `evidence-fingerprint-protocol.md` | 仓库指纹、Evidence freshness 与失效规则 | 验证、复审、基线变化和交付判断 |
| `project-binding-approval-finalization.md` | 项目绑定、Approval、动作读回和 Finalization | Commit、Push、Deploy、Restart、数据写入和最终报告 |
| `quality-validation-gates.md` | 测试选择、最低验证、对抗与性能门禁 | 代码/脚本/前端/迁移修改后的验证阶段 |
| `quality-review-completion.md` | 实施后复审与完成定义 | 代码与验证稳定后的独立复审和完成判定 |
| `quality-production-operations.md` | 生产环境安全操作 | 生产只读、写操作、发布、重启、停止和回滚 |
| `quality-git-delivery.md` | Git、变更记录与最终交付 | 提交、推送、文档、交付报告和停止位置 |

## 加载原则

- 当前阶段先确定主问题域，再读取最少必要 Reference。
- 项目身份、任务状态、Review Packet、Checkpoint 和项目记忆各有唯一 Owner，不手工复制成第二事实源。
- 当前阶段结束后，不继续把无关分片视为活动上下文。
- 具体代码、配置、Git、日志和运行结果始终优先于 Reference 中的通用规则。
