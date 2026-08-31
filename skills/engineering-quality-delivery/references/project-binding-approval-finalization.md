# Project Binding、Approval 与 Finalization

## 1. Project Binding

跨会话、非简单或受保护操作任务，优先使用 `cp-runtime.py project-onboard` 在仓库外建立：

```text
project-profile.json
project-state.json
project-memory.md
```

Task Envelope 应绑定 Project ID、仓库根目录和 Profile hash。任一项不一致、Profile 完整性失败或仓库发生替换时，停止受保护操作并重新确认。

## 2. Approval 与 Evidence 分离

Approval 是用户或流程对特定操作的明确授权；Evidence 是动作或验证结果的证据。二者不能互相替代。

受保护操作的 Approval 至少绑定：

- Project ID 与 Task ID；
- `commit / push / deploy / restart / data-write / production-operation / make-effective` 中的具体操作；
- `local / nonproduction / production` 环境；
- 当前 Git 基线指纹；
- 过期时间和是否一次性消费。

基线、项目、任务、环境、操作、有效期或消费状态不一致时失败关闭。该机制是工作流级控制，不是 Codex 平台或操作系统的硬权限边界。

## 3. 动作前后协议

```text
Preflight
  → 校验 Project Binding
  → 校验并消费 Approval
  → 执行外部动作
  → Readback 当前实际状态
  → 记录 Action Evidence
  → Finalization
```

工具只负责校验、记录和读回，不代替 Git、部署平台、数据库或生产系统执行动作。

## 4. Finalization Integrity

最终交付分别判断：

```text
modified / validated / reviewed / committed / pushed /
deployed / restarted / effective
```

每个声明都必须有当前基线上的直接证据或动作读回；不支持的声明必须阻断或从最终报告中移除。最终文本从已接受方案与实际状态重新生成，不从完整聊天历史中拼接已被否决的中间方案。
