# V5.1 安装包验证报告

## 1. 验证对象

- 平台：Codex
- 版本：`5.1.0`
- 版本名称：自观察与受控自进化版
- 基线：V5.0 项目治理与证据闭环版
- 环境：Linux x86_64、Python 3、Bash、Git

## 2. 结构与兼容性

- 保留 9 个 Skill 与 7 个专业 Reviewer；
- 保留 V5.0 Project Profile、Task Envelope V2、Approval、Evidence、Finalization、Checkpoint 和 Memory Promotion；
- `runtime/cp_runtime` 仍是唯一共享运行时；
- `runtime/cp_runtime/evolution` 是唯一受控自进化实现；
- 安装器同时管理 `tools/cp-runtime.py` 与 `tools/evolution.py`；
- V5.1 不删除 V5.0 文件，不自动修改业务仓库或现有 `config.toml`。

## 3. 受控自进化边界

已验证：

- `Observation → Analysis → Proposal → Human Decision`；
- 所有 Proposal 的 `execution_authorization = NONE`；
- 不存在 `execute`、`apply`、`autofix`、`self-modify` 或 `auto-accept` 子命令；
- ACCEPTED 只记录人工决定，实施仍需新 Task、Git 基线、Approval、Review 和 Finalization；
- 提案和决策采用追加式哈希链，篡改时失败关闭；
- 数据源限制在项目上下文内，拒绝绝对路径、`..` 和符号链接；
- API Key、Bearer、Cookie、私钥和带凭据连接串在持久化前脱敏；
- Reviewer 退役只能形成高置信度候选，不能自动删除能力。

## 4. 自动化验证入口

```text
python3 -B scripts/validate-v51-evolution.py
python3 -B scripts/semantic-lint.py
python3 -B scripts/routing-eval.py validate
python3 -B scripts/validate-package.py
```

`validate-package.py` 覆盖 Python 编译、专项/回归测试、35 条 Skill 路由用例、隔离安装、幂等重装、Verify、Doctor、Restore、安装后 Evolution CLI、脚本语法、源码树稳定性和 `CHECKSUMS.sha256`。

## 5. 明确未验证项

- Windows PowerShell 5.1/7 实机执行；
- 真实 Codex App、CLI 或 IDE 中的隐式 Skill 路由、真实子 Agent、模型回退与 Token/credits；
- 真实 Commit、Push、部署、重启、生产写入和业务生效；
- Codex、操作系统、云平台或发布平台的硬权限隔离。

## 6. 结论

V5.1 的自动化校验用于证明包内合同、安装流程和受控自进化边界一致；目标环境仍需执行 Windows/Codex/真实项目验收。
