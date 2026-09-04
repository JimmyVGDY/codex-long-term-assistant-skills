# V7.4.5 验证报告

状态：本地验证完成；远端交付待读回。

## 已通过

- 官方版本门：GitHub 稳定 Release 与 npm `latest` 均为 0.153.3，仓库上一公开版本仍声明 0.153.2。
- Windows 活动 CLI：同一 npm 全局路径从 0.153.2 更新到 0.153.3；版本、帮助、登录与 Plugin 列表读回通过。
- 兼容注册表：11 个稳定版，锚点 0.153.3，未来版、预发布版与窗口外版本失败关闭。
- 0.153.3 隔离单元：官方制品 SHA-256、CLI 合同、Plugin 往返与合成 Hook 通过。
- 账户级 Plugin：V7.4.5 事务安装、`HOST_COMPATIBLE`、installed/enabled 读回与 182 文件三方 payload 摘要一致。

## 不在本报告中预先声明

- Ubuntu 与完整 11 版本矩阵由远端 CI 独立执行。
- 标签、Draft、六项资产、GitHub provenance 与公开 Release 必须在推送后读回。
- 本次未执行实际卸载/回滚或父子 Agent 生命周期旅程。
