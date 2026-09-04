# V7.4.3 验证报告

状态：本地候选实现与 Windows 账户级重装验证通过；远程 CI、标签和公开 Release 尚未执行。

## 已验证范围

- 运行时事件、预算、Reviewer、校准、Evolution 与发布报告采用批准派发档位和预留单位，不依赖宿主实际模型身份。
- Event V3 与 Event V2、Budget V2 与 Budget V1 使用独立链；旧链只读验签后执行安全投影。
- Lifecycle Acceptance V2 检查事件顺序、关联、项目隔离、链与封印状态，并检查输出不含宿主模型身份。
- 派发策略验收覆盖允许档位、Terra High 自动上限以及越界请求失败关闭；结果只输出抽象策略结论。
- 隐私边界静态检查覆盖活动代码、配置、当前文档和发布脚本。
- 包级门禁通过 233 项仓库测试与 6 项运行时测试；严格本地化、语义检查和 payload 完整性通过。
- Windows 账户在 Codex CLI 0.153.2 上完成 V7.4.2 到 V7.4.3 事务重装；Plugin 读回为 installed/enabled，10 个 Skill、7 个 Reviewer、6 个 Hook 均可用，无活动事务。
- 源目录、账户 Marketplace 与版本化 cache 各有 182 个受管 payload 文件，三方摘要均为 `a6d083a6bef6a83beacf1d9c27882fe70a0e0b2682fc76e7dc0390f5328d72af`。
- 已安装 `cp_hook.cmd` 完成 5 条父子生命周期实测，SessionEnd 形成 `SEALED_CURRENT`，封印覆盖 5/5 记录；报告未读取或导出宿主模型信息、原始会话/任务 ID 或正文。
- 实装发现并修复 payload 复制旧 Python 字节码与 Windows 长路径签名 job 失败；最终重装及 Hook 运行后 Marketplace/cache 均无 `.pyc` 残留。
- 账户卸载 dry-run 通过受管哈希与备份清单检查；未执行实际卸载或回滚。
- 内部链接审计覆盖 514 个 Markdown 文件、572 个链接，0 Finding、0 Warning。
- 中英文候选 ZIP 均完成两次构建摘要一致性验证，并分别通过归一化元数据和包内版本检查。
- 实施后独立复审的阻塞根因已集中修复并由原 Finding Reviewer 复核关闭；最终结论为逻辑只读复审完成、无阻塞项。

## 尚待最终读回

- 完整 Windows/Ubuntu CI 与固定 Codex 版本矩阵；
- 账户级实际卸载/回滚与 Release Attestation；隔离安装/回滚已由自动化测试覆盖；
- `origin/main`、`v7.4.3` 标签与公开 Release。

上述项目不得从 V7.4.2 的历史证据继承为 V7.4.3 已通过。
