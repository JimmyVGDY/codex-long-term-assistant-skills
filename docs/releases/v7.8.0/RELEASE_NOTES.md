# V7.8.0 发行说明

本版本把“装完即可使用、增强能力按条件自动适配”落实为可验证合同，同时保留 V7.6.2 的消息非阻断边界和 V7.7.0 的 Operation v2 写前保护。

- 新增 `capability-registry/1`，固定 C01-C25 能力、入口、默认 AUTO/BASIC、前提、持久化、同意、退路和风险引用。
- 新增仓库外能力偏好。缺文件即 AUTO 且不落盘；显式 OFF、最高档位和 LIGHT/STANDARD/STRICT 风险相互独立，任何档位都不授予外部动作权限。
- 新增 `onboarding/1` 与独立扫描任务状态：一次询问、nonce/revision CAS、过期续期、选择幂等、取消 epoch、租约 fencing、三次接管上限和晚到结果拒绝。
- 新增范围复审伴随清单。目标、静态依赖、配置和权威文件指纹决定 freshness；动态依赖未知时为 `INCOMPLETE`，范围 PASS 不等于全仓发行 PASS。
- 安装器在本地模块导入前检查 Python 3.11+；Windows 包装器和 Hook 启动器验证实际解释器版本。
- `doctor` 增加总体与分功能检查、修复建议及 strict 行为；新增只读 `inventory`；无 state 卸载 dry-run 为零删除预览，真实卸载继续拒绝。
- 安装状态保存来源分类，项目绑定后通过精确 CAS 惰性迁移偏好；旧门禁、GateTask 和 Operation 证据永不成为 AUTO、FULL、授权或扫描同意。

首次全扫可以跳过。拒绝、未回答、缺 Profile/索引/Reviewer、辅助状态不可写或子 Agent 不可用时，普通任务仍走当前源码和 BASIC 路径；缺少必需独立复审时只把该交付门槛标为未完成。
