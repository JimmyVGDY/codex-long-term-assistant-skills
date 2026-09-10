# V7.7.0 验收记录

核验日期：2026-09-10。以下记录绑定最终候选；结果发生变化时必须重新运行对应验证。

| 项目 | 当前结果与边界 |
|---|---|
| Operation v2 | 合成 Git 仓库覆盖 A 拒绝、已有引用准备、B 原子领取、PostTool 对账、完成与证据失效；旧 GateTask 不参与新许可。 |
| 规范 Patch 适配 | 覆盖 Add/Delete/Update/Move、多目标、UTF-8 字节预算、路径边界、链接/父目录变化、前态变化和 8 MiB 单目标上限；正文不落盘。 |
| 取消与异常 | READY 前取消为 CANCELLED；许可后取消、策略变化、时钟回退、PostTool 错误或缺失回执收敛为 OUTCOME_UNKNOWN。 |
| 兼容证据 | 在线复核 11/11 PASS：官方 async、Pre/Post schema、成功 ApplyPatchToolOutput、PostTool payload 和字符串响应源码均匹配冻结 tag、commit 与 SHA-256；外部报告 SHA-256 为 `b6663db0f194c8b58b698b05c95b7def2903bd22d73d39ee670a45dd77828591`。 |
| 定向与完整测试 | Operation 16 项、Hook 19 项、安装器与兼容 59 项均 PASS；最终完整包装器 PASS：327 项 package + 179 项 runtime，Python 3.13.15。早一轮 runtime 的符号链接创建专项曾按环境能力跳过；最终数量以包装器汇总为准。 |
| 性能 | disabled/unconfigured 文件门禁 50 次真实进程调用：p50 82.15 ms、p95 92.05 ms、p99/max 269.76 ms。启用强制路径另受 Git、哈希与宿主 5 秒短超时约束。 |
| 未覆盖范围 | Hook 无法与工具副作用组成原子事务；shell/MCP/未知写入口、账户安装、Desktop 重启和原项目现场行为需分别验证。 |

本地候选实现、测试、在线来源复核和第二轮逻辑只读复审已闭合。提交、推送、标签、公开附件、账户安装、重启和实际生效状态仍须在对应动作后分别读回。
