# V7.13.4 发行说明

V7.13.4 将冻结兼容窗口推进到官方稳定版 Codex CLI 0.157.0，并保留产品仅支持 Codex Desktop 的边界及 V7.13.3 的 Windows 路径身份修复。

- 冻结 0.157.0 至 0.153.0 的十一版本窗口；0.152.1 移出活动窗口。
- 登记官方 npm integrity、tarball SHA-256、标签提交 `00c972ed5d6ff6499317fd41b7f23605b8e6850d`，并以 `result-v156` 复用未变化的 Hook/apply_patch 源码摘要。
- 记录上游 GPT-6 Sol/Luna 与 Bedrock、全屏 transcript、后台服务自动启动、会话 fork/import、渲染改进及网络、语音、上传修复。
- 保留冻结 V3 默认、GPT-5.6 兼容、V7.13.1 恢复保护和 V7.13.3 Windows 根路径标准化。
- 部署公开 Plugin/runtime 载荷时保留继承的只读 ACL，同时继续保持状态、备份和 Marketplace 元数据私有。
- 规范化 Desktop collaboration 工具名，并登记明确的 bare、dotted、concatenated Pre/Post matcher，不使用生产 wildcard matcher。

原生 V4 reentry denial 已验证。Desktop 将消息正文作为不透明加密值传输，因此精确明文正文绑定仍未验证，原生正向准入继续阻断。本版本不削弱正文校验、不伪造回执、不启用 GPT-6 默认，也不宣称模型资格或原生正向 PASS。

提交、推送、安装、CI、标签、Release、资产、provenance 与公开生效必须分别读回。
