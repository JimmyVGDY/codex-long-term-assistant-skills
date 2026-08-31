# V6.6 审计报告

## 结论

V6.6 将 V6.5 的诊断模型口径固化为可执行契约，并把事件完整性扩展到多进程崩溃恢复、SessionEnd 延迟封印和非破坏归档。当前宿主无法证明实际运行模型，此状态明确保留为 `UNAVAILABLE`。

## 关键审计项

- 模型证明：无外部宿主信任锚时拒绝 VERIFIED；诊断 JSONL 不参与证明。
- 锁：使用 Windows byte-range lock / POSIX flock；进程退出自动释放，不删除 stale lock 文件。
- keyring：临时文件、fsync、原子 replace；旧 key 只转 RETIRED，不删除。
- 队列：签名 job、稳定幂等键、pending/running/done/dead-letter 状态、固定错误码。
- Worker lease：同时绑定 PID 与进程创建标识，PID 复用不能阻止恢复。
- Seal 发布：完整临时文件 fsync 后原子 replace，故障保持 old-or-new 有效状态。
- Windows Hook：完整引用 Plugin 启动路径，空格路径已运行验证。
- 归档：同一 event lock 下冻结 segment 前缀，副本与不可变 manifest 均校验哈希。
- 健康概览：专用 allowlist DTO，不透传路径、异常正文或事件 metadata；单项目损坏不阻断其他项目。
- 演进：不自动修改 Skill、Reviewer、路由、全局规则或业务代码。

## 审查与验证

- 6 名逻辑只读 Reviewer 分别覆盖实施前设计、实施后并发/安全与修复定向复核。
- 实施后发现的 SessionEnd 静默失败、PID 复用、seal 半行、路径引用和 reparse 根因已集中修复。
- 92 项 package、6 项 runtime 与 17 项 V6.6 深化专项通过。
- 实际 Reviewer 模型与强度仍为 `UNVERIFIED`；请求档位未作为运行事实。

## 仍受宿主约束的事项

可信实际模型证明需要后续宿主直接提供可关联且可验证的字段。包内契约正例只证明接入能力，不代表 Codex 0.150.1 已具备该字段。
