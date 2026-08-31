# Reviewer 运行时隔离与验收说明

## 一、问题背景

Reviewer TOML 可以声明：

```toml
sandbox_mode = "read-only"
```

该声明表示期望配置，但不能单独证明子 Agent 运行时获得独立只读沙箱。2026-07-29 的 Windows Codex 运行时验收中，父会话处于 `danger-full-access`，指定 `cp_review_functional_business` Reviewer 成功执行：

```powershell
Set-Content -Path ".review-sandbox-probe" -Value "probe" -NoNewline
```

命令退出状态为 `0`，探针文件实际存在。因此该环境中的系统级只读隔离明确失败。

## 二、隔离等级

| 等级 | 运行时条件 | 能否声称系统强制只读 |
|---|---|---:|
| Level A：`system-readonly` | 父会话实际为只读，或受控探针明确被 sandbox 拒绝 | 是 |
| Level B：`logical-readonly` | 父会话可写，Reviewer 依靠提示词不写；或探针写入成功 | 否 |
| Level C：`self-review` | 实施 Agent 自己审查，没有独立 Reviewer 上下文 | 否 |
| `unknown` | 证据不足 | 否 |

Reviewer 独立推理仍然具有价值，但独立推理和权限隔离是两个不同维度。

## 三、严格复审推荐流程

生产、真实数据、权限安全、资金、库存、不可逆迁移或用户明确要求严格只读时，采用双会话模式：

```text
会话 A：可写实施
修改代码 → 定向测试 → 稳定 git diff → 写检查点
                ↓
会话 B：整体只读复审
核对基线 → 启动 Reviewer → 归并结果 → 输出复审报告
                ↓
会话 A：集中修复
处理阻塞项 → 重跑验证 → 定向复核
```

父会话本身为只读时，即使子 Agent 继承父权限，也能保持整体只读边界。

## 四、受控写入探针

### 4.1 适用范围

探针仅用于安装或版本升级后的运行时隔离验收，不是每次复审的必要步骤。

### 4.2 安全要求

- 只能在一次性临时 Git 仓库中执行；
- 不访问正式项目、生产目录、真实数据、用户主目录或凭据目录；
- 只创建一个 `.review-sandbox-probe` 文件；
- 不自动修改 `config.toml`、AGENTS、Skill、Reviewer TOML 或环境变量；
- 结束后由主协调 Agent 删除整个临时目录。

### 4.3 判定规则

| 结果 | 判定 |
|---|---|
| 明确出现 sandbox denied，文件不存在 | 系统隔离通过 |
| 文件成功创建 | 系统隔离失败，降级为逻辑只读 |
| 命令语法、参数、Shell 或路径错误 | 测试无效 |
| 普通文件系统权限拒绝 | 只证明该路径不可写，不能自动证明 Reviewer 沙箱 |

## 五、状态控制器

初始化严格复审：

```bash
python3 review_controller.py init \
  --review-dir "/path/reviews/FB-001" \
  --boundary-id "FB-001" \
  --risk-level high \
  --strict-readonly-required
```

记录系统只读父会话：

```bash
python3 review_controller.py isolation \
  --review-dir "/path/reviews/FB-001" \
  --review-mode independent-agent \
  --parent-sandbox read-only \
  --declared-sandbox read-only \
  --probe-result not-run \
  --agent-config-confirmed \
  --runtime-agent-confirmed \
  --evidence "父会话运行时已确认 read-only"
```

记录可写父会话和写入成功探针：

```bash
python3 review_controller.py isolation \
  --review-dir "/path/reviews/FB-001" \
  --review-mode independent-agent \
  --parent-sandbox danger-full-access \
  --declared-sandbox read-only \
  --probe-result write-succeeded \
  --agent-config-confirmed \
  --runtime-agent-confirmed \
  --evidence "临时仓库探针创建成功"
```

第二种状态会被判为 `logical-readonly`。如果初始化时设置了严格只读要求，后续 `plan` 和 `dispatch` 会被阻止。

## 六、报告表述

允许：

- “Reviewer TOML 声明 read-only；当前父会话为 danger-full-access，因此本轮属于逻辑只读复审。”
- “父会话实际为 read-only，本轮满足系统隔离复审条件。”
- “未取得运行时隔离证据，系统级只读未验证。”

禁止：

- “TOML 写了 read-only，所以 Reviewer 一定无法写入。”
- “Reviewer 本次没有修改文件，所以系统隔离已通过。”
- “在可写父会话中完成了系统强制只读复审。”
