# Codex Skills 使用示例（v3.3）

## 一、本地日志文件分析

```text
使用 $log-observability-analysis。

分析当前目录中的应用日志、轮转日志和压缩日志包。先列出文件、大小、
时间范围、时区、编码和完整性；在不覆盖原文件的前提下分块处理。
建立异常聚类、跨文件时间线和证据台账，区分已确认、高概率、推测和未验证。
输出时脱敏，不把时间相关性直接写成根因。
```

## 二、生产只读跨组件日志分析

```text
使用 $log-observability-analysis、$backend-engineering
和 $data-middleware-infrastructure。

只在生产执行当前授权范围内的只读日志、监控和低风险状态查询。
分析最近 60 分钟应用、HikariCP、MySQL、RabbitMQ 和容器日志，统一时区并
通过 traceId/时间线关联。禁止修改、清理、重启、部署、切流和任何数据写入；
禁止无限 tail -f、无边界扫描、KEYS * 和高消耗全表查询。
```

## 三、跨会话日志排障

```text
使用 $log-observability-analysis 和 $long-running-task-memory。

按应用、数据库、中间件和基础设施来源并行只读分析，由主 Agent 统一时间线、
证据等级和候选根因。每完成一个可恢复节点就追加 PROGRESS.md 并刷新
CURRENT_TASK.md；子 Agent 不修改共享记忆。
```

## 四、Java 本地修复、持续检查点和严格复审

```text
使用 $backend-engineering、$data-middleware-infrastructure、
$engineering-quality-delivery、$multi-agent-independent-review
和 $long-running-task-memory。

全面阅读相关调用链后修复当前接口问题，保留原有业务逻辑。
每完成一个可独立恢复的小节点，立即更新 CURRENT_TASK.md 和 PROGRESS.md；
已完成节点不能只保留在对话中。

完成相关后端定向测试后，按当前风险选择不同职责的 Reviewer，并记录本轮是 system-readonly 还是 logical-readonly。
第一轮结果全部返回前不要零散修改。由主协调 Agent 统一去重、根因聚类、
冲突裁决和分级，形成最小完整修复集合后集中修改。
最多 3 轮复审和 3 轮集中修复，达到上限时如实停止并报告。
更新项目已有 CHANGELOG，创建本地提交但不要推送。
```

## 五、只读多 Agent 全方位复审

```text
使用 $multi-agent-independent-review、$backend-engineering
和 $data-middleware-infrastructure。

只读审查当前分支相对基线的真实 git diff。根据风险从功能业务、
回归兼容、权限安全、性能资源、数据契约、状态并发、测试交付中选择
必要 Reviewer，默认并行最多 3 个；测试/兼容扫描优先 Luna，业务和高风险判断按需使用 Terra，自动最高 Terra High。本轮全部返回后统一归并。

不要修改任何文件，不要创建提交、推送、部署、重启或写数据。
最终输出阻塞项、非阻塞项、未验证项和建议的最小完整修复集合。
```

## 六、跨会话大型改造

```text
使用 $long-running-task-memory、$engineering-quality-delivery
和当前技术栈对应 Skills。

先读取或初始化仓库外的外部记忆文档。把对话上下文视为当前小节点的
临时缓存：每完成一个可恢复节点就追加 PROGRESS.md 并刷新 CURRENT_TASK.md；
连续最多 8 个实质性动作必须形成检查点；高风险操作前后分别记录。

上下文压缩、模型切换或会话恢复后，先读取当前授权、任务快照、计划、
最近 3 个检查点和相关决策，再核对分支、HEAD、git status、git diff、
代码、配置和验证证据。存在冲突时先记录状态分歧，不要直接继续修改。
```

## 七、派发 Reviewer 前先写检查点

```text
使用 $multi-agent-independent-review 和 $long-running-task-memory。

当前代码和最低定向验证已经稳定。先写“复审启动检查点”，记录功能边界、
基线、差异范围、Reviewer 清单、轮次、深度和剩余预算；然后并行派发
功能、兼容、安全、性能、数据和并发 Reviewer。子 Agent 不得修改共享记忆，
所有结果由主协调 Agent 收齐后写入复审归并检查点和台账。
```

## 八、编写系统架构设计文档

```text
使用 $technical-document-writing、$backend-engineering、
$ai-engineering 和 $data-middleware-infrastructure。

基于当前仓库实际代码、配置和部署文件编写系统架构设计文档。
不得编造未实现组件；区分已确认事实、推断和未验证项。
包含系统边界、服务职责、数据所有权、接口、缓存、MQ、权限、
部署、监控、容量、风险和演进路线。
```

## 九、基于现有文档全面重构

```text
使用 $technical-document-writing。

完整阅读现有 Markdown 文档，在不改变已确认业务口径的前提下全面重构：
去除重复内容，修正标题层级，统一术语，补充范围、非目标、风险、
验证和回滚。材料没有支持的内容标记为待确认，不要自行补成事实。
```

## 十、Python AI Worker 故障排查和复盘

```text
排障阶段使用 $ai-engineering、$backend-engineering、
$data-middleware-infrastructure 和 $long-running-task-memory；
形成正式报告时退出已完成的技术域，切换到 $technical-document-writing。

只读排查 GPU Worker 间歇停摆。每完成一个明确排除或确认节点就写检查点。
结合日志、进程、线程/协程、队列、数据库连接、NAS I/O、GPU 显存和任务状态
给出多种可能原因、验证步骤、临时止血和正式方案。证据不足的结论标记为
高概率、推测或未验证。最后输出正式故障分析报告。
```

## 十一、生产操作前暂停确认

```text
使用 $engineering-quality-delivery 和 $long-running-task-memory。

先只读检查生产环境和当前版本。写入操作前检查点，记录目标环境、实例、
影响范围、授权、备份、回滚、验收和停止条件。未获得当前任务明确写授权前，
不要执行数据库、Redis、MQ、文件、部署、重启或切流操作。
```


## V4.2 基础能力：模型分级与成本收敛

```text
当前任务使用主 Agent 完成决策。只把相互独立、读取密集且能结构化返回的子任务委派出去。
模型按 luna-low -> luna-medium -> terra-medium -> terra-high 逐级选择；
搜索、提取、测试证据和兼容扫描优先 Luna，业务语义、事务、并发和安全判断再用 Terra。
自动子 Agent 最高不得超过 Terra High，不得自动使用 Sol、xhigh、max 或 ultra。
默认并行不超过 3、累计不超过 6；相同 Reviewer 不重复审查未变化的 packet。
```

## V4.1 基础能力：实施前设计与影响审查

```text
使用 $data-middleware-infrastructure 和 $multi-agent-independent-review。

本次将新增数据库字段、消息字段并回填历史数据。在开始编码和编写迁移脚本前，
先形成目标、非目标、兼容、灰度和回滚方案，再从功能、兼容、数据和性能四个维度
执行一轮只读实施前审查。Reviewer 结果收齐后统一修订方案；实施前审查不能替代
代码完成后的定向测试和独立复审。
```

## V4.1 基础能力：多信号可观测性分析

```text
使用 $log-observability-analysis 和对应技术栈 Skill。

只读关联同一时间窗的应用日志、P95/P99、错误率、连接池、消息堆积、分布式 Trace、
已有 JFR/线程 Dump、告警和发布事件。先统一时区和采样范围，再建立多证据源时间线；
不得因为发布后出现异常就直接认定发布为根因，不要在线上重新采集 Profile。
```

## V4.1 基础能力：最小充分加载

```text
当前阶段先选择一个主领域 Skill，最多补充两个必要辅助 Skill。
不要提前加载后续阶段的 Git、复审、文档和长期记忆流程；
同时需要超过四个 Skill 时，先说明每个 Skill 的唯一职责。
```

## V4.1 基础能力：复审状态控制器

```text
使用 $multi-agent-independent-review 和 $long-running-task-memory。
为当前功能边界初始化 review-state.json。每次计划、派发、收回 Reviewer、归并和集中修复
都更新控制器状态；上下文压缩后先执行 status / validate，未确认剩余预算前不要继续派生。
```


## v3.3：严格只读复审

```text
使用 $multi-agent-independent-review。

本任务涉及生产权限和真实数据，采用 Level A system-readonly。
先确认父会话实际运行在 read-only；若父会话可写，停止派发 Reviewer，
不要仅凭 Reviewer TOML 的 sandbox_mode 声称系统隔离。
记录实际 Agent 类型、配置路径、父会话沙箱、隔离等级和未验证项。
```

## v3.3：可写会话中的逻辑只读复审

```text
使用 $multi-agent-independent-review。

当前父会话为 danger-full-access，因此本轮最多只能标记为 logical-readonly。
Reviewer 仍按行为规则不修改文件、不提交、不派生，但最终报告必须明确：
独立推理已完成，系统级写入隔离没有保证。
```


## V4.1 STANDARD 修复示例

```text
使用 $backend-engineering 和 $engineering-quality-delivery。
采用 STANDARD 档位，先形成任务执行信封；完成相关定向测试并绑定证据指纹。
只有风险需要时才启动 Reviewer，Reviewer 使用独立上下文和统一审查包。
```

## V4.1 STRICT 迁移示例

```text
使用 $data-middleware-infrastructure、$engineering-quality-delivery、
$multi-agent-independent-review 和 $long-running-task-memory。
采用 STRICT 档位，先完成实施前审查和回滚设计；实施后在独立上下文中并行复审，
所有 Reviewer 使用同一 packet hash，阻塞项解决后才进入交付。
```
