# V6.5 审计报告

状态：包内静态与自动化审计完成；正式宿主状态以包外升级报告和 attestation 为准。

## 审计结论

- 宿主 JSONL 被限定为诊断旁证，不能独立满足模型合规结论。
- 统一发行验证与 attestation 校验已安装 PreToolUse 模型门禁报告；真实生命周期与模型策略证明分离，不因宿主缺失实际模型字段而降级信任口径。
- 事件完整性采用 detached seal，避免 V6.4/V6.5 混合写入产生签名降级死链。
- Windows DPAPI 与 POSIX 0600 边界明确；backend、binding 和 issuer 不匹配时失败关闭。
- Keyring 不提供 secret export、delete 或自动清理能力。
- Reviewer 结果缺少稳定身份时不进入校准；重放去重，身份冲突进入 `CONFLICT`。
- TaskOutcomeEvent 2.0、项目双重隔离、模型门禁和受控演进授权边界保持兼容。
- 未发现主 Agent 模型写入或 Reviewer TOML 模型固化。

## 独立审查

实施前安全与兼容审查共识别 5 个阻断点和 1 个非阻断兼容项。全部进入修订设计和测试矩阵。实施后复审结果在正式交付报告中单独记录。
