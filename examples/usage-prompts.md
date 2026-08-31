# Codex Skills 使用示例（v3.0）

## 一、Java 本地修复、持续检查点和严格复审

```text
使用 $java-backend-engineering、$data-middleware-ai-infrastructure、
$engineering-quality-delivery、$multi-agent-independent-review
和 $long-running-task-memory。

全面阅读相关调用链后修复当前接口问题，保留原有业务逻辑。
每完成一个可独立恢复的小节点，立即更新 CURRENT_TASK.md 和 PROGRESS.md；
已完成节点不能只保留在对话中。

完成相关后端定向测试后，按当前风险选择不同职责的只读 Reviewer。
第一轮结果全部返回前不要零散修改。由主协调 Agent 统一去重、根因聚类、
冲突裁决和分级，形成最小完整修复集合后集中修改。
最多 3 轮复审和 3 轮集中修复，达到上限时如实停止并报告。
更新项目已有 CHANGELOG，创建本地提交但不要推送。
```

## 二、只读多 Agent 全方位复审

```text
使用 $multi-agent-independent-review、$java-backend-engineering
和 $data-middleware-ai-infrastructure。

只读审查当前分支相对基线的真实 git diff。根据风险从功能业务、
回归兼容、权限安全、性能资源、数据契约、状态并发、测试交付中选择
必要 Reviewer，并行执行但最多 6 个。本轮全部返回后统一归并。

不要修改任何文件，不要创建提交、推送、部署、重启或写数据。
最终输出阻塞项、非阻塞项、未验证项和建议的最小完整修复集合。
```

## 三、跨会话大型改造

```text
使用 $long-running-task-memory、$engineering-quality-delivery
和当前技术栈对应 Skills。

先读取或初始化仓库外的外部记忆文档。把对话上下文视为当前小节点的
临时缓存：每完成一个可恢复节点就追加 PROGRESS.md 并刷新 CURRENT_TASK.md；
连续最多 5 个实质性动作必须形成检查点；高风险操作前后分别记录。

上下文压缩、模型切换或会话恢复后，先读取当前授权、任务快照、计划、
最近 5 个检查点和相关决策，再核对分支、HEAD、git status、git diff、
代码、配置和验证证据。存在冲突时先记录状态分歧，不要直接继续修改。
```

## 四、派发 Reviewer 前先写检查点

```text
使用 $multi-agent-independent-review 和 $long-running-task-memory。

当前代码和最低定向验证已经稳定。先写“复审启动检查点”，记录功能边界、
基线、差异范围、Reviewer 清单、轮次、深度和剩余预算；然后并行派发
功能、兼容、安全、性能、数据和并发 Reviewer。子 Agent 不得修改共享记忆，
所有结果由主协调 Agent 收齐后写入复审归并检查点和台账。
```

## 五、编写系统架构设计文档

```text
使用 $technical-document-writing、$java-backend-engineering、
$python-backend-ai-engineering 和 $data-middleware-ai-infrastructure。

基于当前仓库实际代码、配置和部署文件编写系统架构设计文档。
不得编造未实现组件；区分已确认事实、推断和未验证项。
包含系统边界、服务职责、数据所有权、接口、缓存、MQ、权限、
部署、监控、容量、风险和演进路线。
```

## 六、基于现有文档全面重构

```text
使用 $technical-document-writing。

完整阅读现有 Markdown 文档，在不改变已确认业务口径的前提下全面重构：
去除重复内容，修正标题层级，统一术语，补充范围、非目标、风险、
验证和回滚。材料没有支持的内容标记为待确认，不要自行补成事实。
```

## 七、Python AI Worker 故障排查和复盘

```text
使用 $python-backend-ai-engineering、$data-middleware-ai-infrastructure、
$technical-document-writing 和 $long-running-task-memory。

只读排查 GPU Worker 间歇停摆。每完成一个明确排除或确认节点就写检查点。
结合日志、进程、线程/协程、队列、数据库连接、NAS I/O、GPU 显存和任务状态
给出多种可能原因、验证步骤、临时止血和正式方案。证据不足的结论标记为
高概率、推测或未验证。最后输出正式故障分析报告。
```

## 八、生产操作前暂停确认

```text
使用 $engineering-quality-delivery 和 $long-running-task-memory。

先只读检查生产环境和当前版本。写入操作前检查点，记录目标环境、实例、
影响范围、授权、备份、回滚、验收和停止条件。未获得当前任务明确写授权前，
不要执行数据库、Redis、MQ、文件、部署、重启或切流操作。
```
