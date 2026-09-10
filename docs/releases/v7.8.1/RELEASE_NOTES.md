# V7.8.1 发行说明

本补丁修复 V7.8.0 账户安装后 `inventory` 对全局 `AGENTS.md` 的错误漂移判断。V7.8.0 的 AUTO、首次引导、范围复审、安装自救与 Codex 0.154.0 兼容合同保持不变。

- `managed_hashes` 中的全局 AGENTS 项继续保存本包受管区块哈希；inventory 现在提取唯一 BEGIN/END 区块后再核对，不再拿整文件哈希比较。
- 标记外自有内容可以独立修改且不触发漂移；受管区块变化、重复或缺失标记仍返回 `DRIFT`，越界路径和重解析点仍失败关闭。
- V7.8.0 已公开且保持不可变；本修复以独立 V7.8.1 版本、PR、标签、Release 和实际安装读回交付。
- 新增 `capability-registry/1`，固定 C01-C25 能力、入口、默认 AUTO/BASIC、前提、持久化、同意、退路和风险引用。
- 冻结兼容窗口继承 V7.7.1：`0.154.0` 至 `0.150.0` 共 11 个稳定版本，保留 0.154.0 专属 `result-v154` 和 canonical registry digest 校验。
- 新增仓库外能力偏好。缺文件即 AUTO 且不落盘；显式 OFF、最高档位和 LIGHT/STANDARD/STRICT 风险相互独立，任何档位都不授予外部动作权限。
- 新增 `onboarding/1` 与独立扫描任务状态：一次询问、nonce/revision CAS、过期续期、选择幂等、取消 epoch、租约 fencing、三次接管上限和晚到结果拒绝。
- 新增范围复审伴随清单。目标、静态依赖、配置和权威文件指纹决定 freshness；动态依赖未知时为 `INCOMPLETE`，范围 PASS 不等于全仓发行 PASS。
- 安装器在本地模块导入前检查 Python 3.11+；Windows 包装器和 Hook 启动器验证实际解释器版本。
- `doctor` 增加总体与分功能检查、修复建议及 strict 行为；新增只读 `inventory`；无 state 卸载 dry-run 为零删除预览，真实卸载继续拒绝。
- Windows inventory 在归属判断前规范化设备前缀、短路径与大小写别名，避免正常受管文件误报 `UNSAFE_PATH`；越界路径和重解析点仍失败关闭。
- 安装状态保存来源分类，项目绑定后通过精确 CAS 惰性迁移偏好；旧门禁、GateTask 和 Operation 证据永不成为 AUTO、FULL、授权或扫描同意。

首次全扫可以跳过。拒绝、未回答、缺 Profile/索引/Reviewer、辅助状态不可写或子 Agent 不可用时，普通任务仍走当前源码和 BASIC 路径；缺少必需独立复审时只把该交付门槛标为未完成。
