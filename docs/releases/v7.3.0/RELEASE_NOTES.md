# V7.3.0 发行说明

English: [RELEASE_NOTES.en.md](RELEASE_NOTES.en.md)

版本：7.3.0

## 核心变化

- Reviewer 派发新增 `minimum_acceptable_profile`。实际档位低于最低可接受档位时，结果只能保持 `incomplete`，不能正常归并或关闭。
- 新增追加式 `INLINE/DELEGATE` 决策门；`INLINE` 不创建 Reviewer 轮次，也不消耗 Reviewer 预算，后续改判通过新决策记录保留完整轨迹。
- Reviewer 结果合同升级到 schema v3，记录任务难度、耗时、待最终化归因、finding 处置和 `profile-weight-v1` 估算成本；归因只能由控制器根据归并结果最终化。
- 受控演进按 Reviewer、模型档位和任务难度汇总成本与收益。缺失成本保持 unknown，未最终化归因不参与低收益判断，真实样本不足时保持默认路由不变。
- Plugin 模式启动器只加载安装状态绑定的版本化缓存，历史 standalone runtime 不再抢先覆盖当前 Plugin 策略；目标缓存缺失时失败关闭。
- 双语文档站、当前导航、安装恢复和发行脚本统一到 V7.3.0，V7.2.0 及更早内容继续作为历史证据保留。

## 不变安全边界

- `execution_authorization=NONE`
- 自动子 Agent 仍限制在 Luna / Terra，自动上限保持 `gpt-5.6-terra + high`
- Skill 激活不扩大文件、Git、环境、生产或数据权限
- Reviewer 自报不能最终化自身归因，成本缺失不能被当作零成本
- 未验证 Codex CLI 版本的 Plugin 安装继续失败关闭

## 验收边界

包级回归、真实数据校准观察、本机 Plugin 安装、Git 提交、远端推送、标签、GitHub Release 公开状态和下载后制品核对分别记录。任一阶段的 PASS 不替代其他阶段的动作与读回证据。
