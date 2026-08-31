# v3.2 安装包验证报告

## 一、验证对象

- 安装包：Codex 跨项目长期技术助手 Skills 安装包
- 版本：`3.2.0`
- 版本名称：P0 调度与执行确定性增强版
- 验证日期：2026-07-29
- 验证环境：Linux 容器，Python 3、Bash、Git 可用；PowerShell 不可用

## 二、本次 P0 范围

- 全局增加最小充分 Skill 加载、阶段化激活和活动 Skill 数量上限；
- 多 Agent 复审增加实施前设计与影响门禁；
- 新增 `review_controller.py`，持久化并强制校验 pre/post 轮次、深度、Reviewer 数量和集中修复轮次；
- 日志 Skill 扩展 Metrics、Trace、Profiling、告警和发布/配置变更事件；
- 新增 3 个可观测性模板，日志与可观测性模板总数为 6；
- 外部记忆增加明文凭据扫描、POSIX 权限收紧和只读保留期报告；
- 新增 16 条 Skill 路由回归用例和 `routing-eval.py` 观察评分工具；
- 更新 Manifest、全局调度、Skill 边界、README、模板和安装验证脚本。

## 三、自动验证结果

执行命令：

```bash
python3 scripts/validate-package.py
```

结果：**通过，1 项环境限制警告，无验证错误。**

| 验证项 | 结果 |
|---|---|
| Manifest | `3.2.0`，9 个 Skills，7 个 Reviewer，P0 参数一致 |
| 全局 `AGENTS.md` | 22,894 bytes，受管标记、最小加载、实施前门禁和多信号可观测性规则通过 |
| Skills | 9 个 `SKILL.md` Frontmatter、名称、description 和相对引用通过 |
| Skill 元数据 | 9 个 `agents/openai.yaml` 结构检查通过 |
| 自定义 Reviewer | 7 个 TOML 通过，均保持 `read-only` 并禁止继续派生 |
| 正式文档模板 | 12 个通过 |
| 外部记忆模板 | 10 个通过 |
| 复审模板 | 4 个通过，包含实施前审查模板 |
| 可观测性模板 | 6 个通过 |
| Markdown | 代码块闭合、相对引用和硬编码个人路径检查通过 |
| Shell 脚本 | 5 个语法检查通过 |
| PowerShell 脚本 | 5 个静态结构检查通过 |
| 检查点工具 | `init / append / validate / recover / repair / archive / security-check / secure / retention-report` 实际运行通过 |
| 敏感信息检测 | 人工构造测试凭据能够被阻止，删除测试数据后恢复通过 |
| POSIX 权限 | `secure` 实际将目录设为 700、文件设为 600 |
| 复审控制器 | pre/post 计划、派发、结果、归并、修复、状态、关闭和实施前轮次上限实际运行通过 |
| 路由用例工具 | 用例结构、观察模板和评分流程实际运行通过 |
| 用户级安装 | 首次安装、重复升级、验证、卸载实际运行通过 |
| 仓库级安装 | Skills + Reviewer 安装和卸载实际运行通过 |
| 第三方资源保护 | 安装和卸载未误删模拟的第三方 Skill、Agent 和用户原有规则 |

## 四、P0 专项验证

### 4.1 最小充分加载

静态检查已确认全局存在：

```text
PRIMARY_DOMAIN_SKILL_LIMIT = 1
DEFAULT_SUPPORTING_SKILL_LIMIT = 2
MAX_ACTIVE_SKILLS_WITHOUT_JUSTIFICATION = 4
```

`tests/skill-routing-cases.json` 覆盖只读解释、代码修复、生产日志、Metrics、Trace、Profiling、文档、长期任务、实施前审查和实施后复审。

**限制：** 当前环境没有运行真实 Codex 客户端，因此未声称隐式 Skill 自动激活结果已经通过。必须在实际 Codex 中逐条观察并使用 `routing-eval.py evaluate` 评分。

### 4.2 实施前与实施后门禁

已检查：

- 实施前最多 1 轮、2～4 个 Reviewer；
- 实施后最多 3 轮；
- 全部阶段共享累计 12 个 Reviewer 预算；
- 实施前审查不能替代最低定向验证和实施后复审；
- `review_controller.py` 能阻止第二轮实施前审查。

### 4.3 多信号可观测性

已检查范围：

- Logs；
- Metrics；
- Distributed Traces；
- Profiles / Dumps；
- Alerts；
- Deployments / Configuration Changes。

在线 Profiling、扩大生产采集和临时写入仍保持独立授权。

### 4.4 外部记忆安全

已检查：

- 常见明文凭据模式扫描；
- POSIX 权限检查和收紧；
- 默认完成任务 90 天、临时分析 30 天建议值；
- `retention-report` 只报告候选，不自动删除；
- Windows ACL 和企业 DLP 不由 Python 脚本冒充完成。

## 五、未完成的环境验证

### Windows PowerShell

当前环境没有 PowerShell，因此：

- 已完成 PowerShell 静态结构检查；
- 未执行 PowerShell 5.1 / 7 解析器检查；
- 未在 Windows 本机实际执行安装、升级、验证和卸载。

Windows 安装后应执行：

```powershell
powershell -ExecutionPolicy Bypass -File ".\scripts\verify-user-install.ps1"
```

### Codex 真实路由

结构化路由用例和评分工具已经验证，但真实隐式激活需要在用户 Codex 客户端完成：

```bash
python3 scripts/routing-eval.py make-template --output routing-observations.json
# 在 Codex 中逐条运行并填写 activated
python3 scripts/routing-eval.py evaluate --results routing-observations.json
```

## 六、结论

**v3.2 包结构、9 个 Skills、7 个只读 Reviewer、最小充分加载规则、实施前和实施后双门禁、复审状态控制器、多信号可观测性、外部记忆安全工具、路由回归工具、Shell 安装升级流程和仓库级安装卸载流程均通过当前环境可执行验证。**

Windows PowerShell 实机安装和 Codex 真实隐式 Skill 激活属于明确未验证项，未表述为通过。
