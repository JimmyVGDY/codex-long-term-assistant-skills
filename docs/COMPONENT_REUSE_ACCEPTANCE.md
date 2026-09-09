# 组件与模块复用验收

本规程验证 [公共复用规则](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/blob/v7.6.0/skills/engineering-quality-delivery/references/component-module-reuse.md)。适用于本包维护者；不由普通业务任务自动执行。

## 准备与执行

使用 `scripts/reuse-eval.py prepare --case <场景> --output <仓库外新目录>` 准备当前候选；增加 `--baseline <已确认提交>` 准备历史规则，增加 `--locale en` 准备英文规则。每次独立目录，目录已存在时拒绝覆盖。`tests/reuse-fixtures.json` 提供业务输入，`tests/reuse-oracles.json` 保存验收断言，只由评估者读取。

给执行 Agent 仅提供 `workspace` 路径、`prompt.txt` 中的任务目标和一致的运行/写入边界。让它通过工作区的 `.agents/skills` 加载适用规则，不提示复用答案，不提供 oracle、前次结果或其他场景。记录规则哈希、场景初始哈希、请求模型/强度、开始结束时间及可获得的读取/执行计数；没有宿主证据的指标保留 UNKNOWN。模型设置是实验控制项，不冒充宿主实际模型证明。

优化前后使用同一模型、强度、任务、初始应用文件和工具权限。关键场景（直接组件复用、兼容扩展）各 3 次，其余场景至少 1 次；不得用同一上下文续问替代独立回放。隔离是目录及行为约束，未证明运行时隔离时只称逻辑隔离。

执行结束后调用 `scripts/reuse-eval.py verify --output <对应目录>`。它在临时副本运行原测试和隐藏行为断言，检查原测试及规则未被改写，并记录应用差异；不把断言写回执行目录。不运行网络、安装、发布或真实业务接口。样例使用已安装的 Python/Node，前端为无依赖 ES Module 组件，不能据此声称覆盖 Vue/React 或浏览器完整交互。

## 人工判定矩阵

| 场景 ID | 判定实际源码和证据 |
|---|---|
| direct-component | Settings 调用已有 action，未复制按钮转义和属性规则 |
| different-name | invoice 使用 present_minor，未重新实现金额规则 |
| similar-different | 严格安全码未沿用营销的宽松规范化，营销旧行为不变 |
| compatible-extension | 同一 badge 支持 compact，旧调用和默认转义保持不变 |
| permission-state | 门户始终按当前租户筛选，不复用跨租户缓存或管理员全量出口 |
| shared-extraction | cart/quote 依赖同一个运费规则，原公开入口可用 |
| stale-index | 源码确认已移动的 safe_name，未按过期索引另造实现 |
| local-fix | 修复分页空集合，未引入公共抽象或改动无关模块 |

`behavior_passed` 只表示样例行为断言及受保护输入检查通过，`semantic_reuse_review` 默认 UNKNOWN。评估者必须另查实际调用链、代码差异、检索和决策证据，逐项记录发现、无理由重复实现、错误复用、旧用途回归、读取/执行成本。程序不通用判定语义复用；执行者自称通过不是独立证据。

## 门槛与推广

所有候选场景达到预定义行为和语义标准，关键重复场景全部通过，才进入独立复审和安装验收；失败保留原结果、归因后定向修订与复测，不覆盖失败记录。先冻结候选规则再回放，规则改动后受影响结果失效。

包校验、链接、本地化和样例测试分别报告；独立复审使用现有 packet/controller，不引入新运行时合同。获授权安装后核对实际安装内容与候选哈希，并在新的宿主任务中从安装入口加载实测；副本回放不能代替安装验收。没有实际安装或新宿主证据时，保持未完成。有限样本通过不代表普遍稳定，优化前已通过的样例不能据此宣称复用率提升。

相关文档：[能力索引](CAPABILITY_INDEX.md) · [验收规程](COMPONENT_REUSE_ACCEPTANCE.md) · [V7.6.0 验证报告](releases/v7.6.0/VALIDATION_REPORT.md)。
