# V6.2 发行审计报告

审计日期：2026-08-28

## 审计范围

- V6.1 实机修复是否被完整纳入 V6.2，而非仅修改版本号；
- Windows 原生 Codex 0.150.1 Plugin/Marketplace 注册；
- 安装、备份、回滚、卸载、未知外部文件保护与长路径行为；
- 10 Skills、7 Reviewers、6 Hooks 与 TaskOutcomeEvent V2；
- 模型成本上限、自观察隔离和受控演进授权边界。
- 自然语言中性化及机器契约兼容边界。

## 结论

审计通过。V6.2 将 V6.1 现场修复正式固化，并增加 Windows extended-length path 支持和相应回归测试。真实隔离环境已完成 V6.1→V6.2→V6.1 闭环，目标 Plugin 的安装、启用和版本均由 Codex CLI 实际读回确认。

自然语言内容采用中性表达，测试身份使用匿名占位符；`--scope user`、JSON 字段名及路径变量属于机器契约，继续保留以确保兼容。

## 关键断言

- Plugin ID：`codex-cross-project-engineering-assistant@cp-assistant-local`。
- Marketplace：`cp-assistant-local`。
- V6.2 成功条件：`installed=true`、`enabled=true`、`version=6.2.0`。
- 自动子 Agent 仅允许 Luna/ Terra 四档，最高 `gpt-5.6-terra + high`。
- Reviewer TOML 不固定模型；主 Agent 模型配置不由本包覆盖。
- SessionEnd timeout 为 3 秒，Windows Hook 不依赖 `python3.exe`。
- Proposal 永久为 `execution_authorization=NONE`，人工 ACCEPT 也不等于执行授权。
- 安装失败按受管目标清单回滚；卸载对 AGENTS/standalone Hooks 进行受管内容合并恢复，不删除未知账户 Skill、Agent、Hook、MCP、配置或历史观测数据。

## 证据索引

- `VALIDATION_REPORT_V6.2.md`
- `RELEASE_NOTES_V6.2.md`
- `V6.2_BUILD_INFO.json`
- `tests/test_package_manager_security.py`
- `tests/test_v60_deterministic_observation.py`
- `scripts/package_manager.py`
- `scripts/validate-package.py`
