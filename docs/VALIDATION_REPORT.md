# V4.2 安装包验证报告

## 验证对象

- 平台：Codex
- 版本：`4.2.0`
- 版本名称：模型分级与成本收敛版
- 验证日期：2026-08-12
- 环境：Linux 容器、Python 3.13、Bash 5.2、Git 2.47
- 环境限制：未安装 PowerShell；未连接真实 Codex 客户端运行时

## 验证范围

### 1. 安装包结构与元数据

- 校验 9 个 Skill、7 个只读专业 Reviewer、`manifest.json` 和平台元数据；
- 校验所有 Skill 的 `SKILL.md` 与 `agents/openai.yaml`；
- 校验 Markdown 代码块闭合、Python 脚本语法、必需文件和渐进加载索引长度；
- 校验包内不存在 `__pycache__`、`.pyc` 等运行缓存残留；
- 校验 `CHECKSUMS.sha256` 覆盖所有发布文件且哈希一致。

### 2. 模型分级与成本策略

- 校验四级自动子 Agent 档位完整：
  - `luna-low`
  - `luna-medium`
  - `terra-medium`
  - `terra-high`
- 校验默认模型为 Luna Medium，自动升级链按档位逐级进行；
- 校验自动流程最高为 Terra High；
- 校验 Sol、`xhigh`、`max`、`ultra` 被列为禁止自动使用项；
- 校验 7 个 Reviewer TOML 未写死模型和推理强度，保留运行时动态路由能力；
- 校验 `terra-high` 必须提供风险理由，并受单边界数量预算约束。

### 3. 多 Agent 独立复审

- 校验默认上限：深度 2、实施后最多 2 轮、并行 Reviewer 3、累计 Reviewer 6、集中修复 2 轮、Terra High Reviewer 1；
- 校验 V4.1 高预算只作为显式兼容硬上限，不会被普通流程自动启用；
- 校验相同 Reviewer、相同审查包的重复派发拦截；
- 校验上一轮结论干净时禁止使用同一审查包机械重跑；
- 校验模型请求、实际模型、回退、未验证和不匹配状态进入审查台账；
- 校验模型不匹配必须显式确认后才能关闭；
- 校验审查结果 Schema V2 和旧数据迁移兼容性。

### 4. 审查包与证据复用

- 校验审查包 Schema V3；
- 校验摘要、差异统计、文件状态、完整 diff、读取顺序和新鲜度指纹；
- 校验目标目录非空时默认拒绝覆盖；
- 校验工作区变化后审查包会被判定 stale；
- 校验旧 Schema V2 审查包仍可读取和验证；
- 校验 Reviewer 使用“摘要 → 分配范围 → 必要 hunk → 最小补充上下文”的渐进读取协议。

### 5. 长期任务记忆

- 校验事件驱动写入，而非每个微步骤机械写入；
- 校验同内容指纹的重复追加默认跳过；
- 校验 8 个实质动作未持久化时触发兜底检查点；
- 校验热检查点默认保留 20 条；
- 校验恢复默认只读取最近 3 个检查点，再按需要向前扩展。

### 6. Skill 路由与渐进加载

- 校验 35 条 Skill 路由用例结构和每条用例的最大活动 Skill 预算；
- 校验普通任务默认不超过 4 个活动 Skill；
- 校验大 Reference 使用索引和按需分片，不要求一次性全量加载；
- 校验流程严格度、Reviewer 成本档位和模型推理强度作为三个独立维度处理。

### 7. 自动化测试和安装恢复

实际执行并通过：

```text
frontend-engineering/tests/test_detect_frontend_stack.py
engineering-quality-delivery/tests/test_execution_guard.py
multi-agent-independent-review/tests/test_review_tools.py
long-running-task-memory/tests/test_checkpoint_dedupe.py
scripts/semantic-lint.py
scripts/routing-eval.py validate
scripts/package_manager.py install --dry-run
scripts/package_manager.py install
scripts/package_manager.py verify
scripts/package_manager.py install（幂等重复安装）
scripts/package_manager.py verify（重复安装后）
scripts/package_manager.py doctor
scripts/package_manager.py restore
scripts/install-user.sh all --dry-run（隔离环境）
scripts/install-user.sh all（隔离环境）
scripts/verify-user-install.sh（隔离环境）
scripts/doctor.sh（隔离环境）
scripts/restore-latest-backup.sh（隔离环境）
bash -n scripts/*.sh
```

安装、验证、重复安装、诊断和恢复均在隔离的临时 `HOME` 与 `CODEX_HOME` 中执行，没有修改当前用户环境。

## 总体验证结果

```text
V4.2 安装包验证通过。
```

## 明确未验证项

- Windows PowerShell 5.1 和 PowerShell 7 实机包装脚本；
- 真实 Codex App、CLI 或 IDE 中的隐式 Skill 路由和自定义 Agent 发现；
- 真实多子 Agent 的并行调度、运行时模型回退、Token、缓存和 credits 数据；
- Codex 平台是否严格执行“自动模型白名单”。本安装包能对自身复审控制器的派发进行拒绝和审计，但 Codex 的显式 spawn 配置仍可能覆盖全局默认值；
- Reviewer 的只读隔离仍应在实际 Codex 版本、父会话权限和沙箱环境中做本机验收。

## 结论

V4.2 的结构、模型路由策略、复审预算、审查包复用、长期记忆去重、单元测试、路由回归、安装恢复和语义一致性均在当前环境中通过。真实 Codex 运行时行为和 Windows PowerShell 包装脚本保留为安装后的本机验收项。
