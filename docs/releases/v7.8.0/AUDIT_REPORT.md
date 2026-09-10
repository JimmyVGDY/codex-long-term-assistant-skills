# V7.8.0 审查记录

- 实施前设计审查先发现 C/UX/M 追踪、CAS、租约、取消、索引一致性、迁移与范围 freshness 缺口；修订后由功能和状态 Reviewer 通过，并对 R2 最终合并基线追加兼容性刷新审查。
- 注册表和首次引导使用独立仓库外 schema 与锁，不修改 Profile、Project State、Capability Index、GateTask 或 Operation v2 的旧 schema。
- 偏好和能力档位不授予提交、推送、发布、部署、生产、数据写入或付费调用权限。
- inventory 不读取受管根之外的 state 路径；未知或漂移资产保留。真实无 state 卸载继续失败关闭。
- 范围复审遇到动态或未解析依赖时为 `INCOMPLETE`；发布仍使用全仓 freshness。
- 实施后源码、跨进程故障注入、双系统 Python 3.11/3.13、公开制品和实际安装加载仍需独立证据。
- 实施后首轮发现：DECLINED 已保存但 scan 取消写失败时缺补偿；C20 指向不存在入口且注册表覆盖校验不足。修复后 419+205 全量、onboarding 15、registry 10、30 次锁压力和 8 进程 CAS 压力通过，两位 Reviewer 最终 PASS。
- 合并 V7.7.1 main 后必须保留 Codex 0.154.0 注册表、停用门禁 PostTool 对账、对应兼容测试、账户加载证据和完整历史；V7.8.0 重新执行受影响验证，不复用合并前计数。
