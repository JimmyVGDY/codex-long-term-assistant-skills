# Codex 跨项目长期技术助手 V6.3 审计报告

## 审计范围

审计覆盖 V6.3 相对 V6.2 的行为变化：安装事务、崩溃恢复、Plugin 注册、事件链、生命周期相关性、自观察质量、Reviewer 归因、确定性 ZIP、发行证明和正式文档。

审计边界为逻辑只读 Reviewer；未执行提交、推送、部署、重启或生产操作。

## Reviewer 配置与运行证据

- 请求档位：Luna Medium；
- 实际模型：TaskOutcomeEvent 读回为 `gpt-5.6-luna`；
- 实际推理强度：宿主事件未提供，状态为未验证；
- Reviewer：状态/并发、测试/交付；
- 最大自动模型未超过 Terra High。

## 实施前发现

实施前复审识别以下交付阻断：

1. 发行证明未绑定正式 ZIP、Codex 与 Plugin 状态；
2. 缺少同一真实会话的五事件生命周期证明；
3. 自观察没有可计算的生命周期完整率；
4. Reviewer 收益可能被发现数量替代；
5. ZIP 没有双构建字节一致证据；
6. V6.3 尚无 Codex 0.150.1 升级验收；
7. 新证据格式需要隐私白名单。

对应实现已加入源码和测试；真实宿主验收已在候选包完成后执行。

## 实施后第一轮发现与处理

| 发现 | 等级 | 处理 |
|---|---|---|
| 文件写入到 journal 持久化之间存在崩溃窗口 | 阻断 | 增加逐目标 `_record_applied` 与目标窗口故障注入 |
| 卸载未完整记录注销前 Plugin 状态 | 阻断 | 注销前持久化 active 与 Marketplace 状态 |
| 生命周期只按 task_id 聚合 | 阻断 | 改为 `(session_id, task_id)`，冲突进入证据门禁 |
| session/task 反向指标固定为 0 | 中 | 改为缺失 session binding 计数并保留 task/session 冲突指标 |
| 重复 event_id 可遮蔽尾链损坏 | 中 | 全链校验完成后再去重，尾部损坏失败关闭 |
| 过期锁可能抢占仍存活持有者 | 中 | 检查 PID 存活并二次复核 owner token |
| V6.3 报告文件缺失 | 阻断 | 新增 V6.3 验证报告与审计报告 |
| 校验脚本存在常量 PASS | 阻断 | PASS 改为来自实际测试命令与数量 |
| 测试数量证据未包含 runtime 测试 | 中 | 分别执行并报告 package/runtime 测试集 |

## 实施后第二轮发现与处理

第二轮确认上述事件、锁、Plugin 注销状态和普通目标 journal 项已关闭，同时发现 Plugin Marketplace 内部仍存在“删除后分步重建”窗口。

处理：在独立 staging 中完整生成 Marketplace，计算目标哈希并先写 mutation intent，再进行目标替换；增加替换前、替换后崩溃恢复测试。旧目录未动、目标缺失和新目录已替换三种状态均可确定性识别。

## 当前结论

源码级阻断项已完成实现，53 项包级回归与 6 项 Runtime 回归通过。发行证明补充了证据内容篡改、非法证据路径、HMAC 正误密钥与生命周期跨 parent 顺序错误测试。

正式宿主验收已确认：Codex CLI 0.150.1、Plugin 6.3.0 installed/enabled、10 个 Skill、7 个 Reviewer、6 个 Hook、主配置未变化、历史记录未减少、无活动事务。真实只读会话产生完整五事件序列，Luna Reviewer 实际启动并停止，TaskOutcomeEvent 2.0 哈希链、`project_id` 与 `repo_fingerprint` 均通过验证。

审计状态：正式宿主部分通过。最终发行制品只有在包外机器证明同时验证正式 ZIP 双构建一致、制品哈希、Codex/Plugin 状态、生命周期报告和验证报告哈希后，才可判定为完整通过。
