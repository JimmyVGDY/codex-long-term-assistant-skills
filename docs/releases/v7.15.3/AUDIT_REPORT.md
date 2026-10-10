# V7.15.3 复审记录

范围：Codex `0.162.1` 与 `0.162.0` 官方证据、闭合十一版本窗口、新 `result-v162`、版本与双语投影、Desktop-only 边界及发布门禁。

- 0.162.x 的 discovery/schema 沿用 0.161.0 合同；apply_patch handler 漂移由独立 `result-v162` 固定，context 未漂移。
- 0.156.1 与 0.156.0 原子退出；仍由 0.157.x 使用的 `result-v156` 保留，窗口外版本继续失败关闭。
- Desktop host contract、管理 CLI、账户 Plugin 和实际 Desktop 新任务保持独立证据层。
- 实施后兼容复审发现中英文 Plugin 描述仍指向 0.161.0；已同步修复为 0.162.1、恢复中文元数据、重算 payload 摘要、重新安装并由 fresh Desktop 进程读回。完整验证、提交、推送、CI、标签、资产和公开下载分别建立证据，不从本记录预先推导完成。
