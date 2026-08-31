# Skill 自动触发与组合矩阵

## 一、单 Skill 典型触发

| Skill | 应触发示例 | 不应单独触发示例 |
|---|---|---|
| `java-backend-engineering` | “分析这个 Spring 事务为什么没生效” | 纯 Vue 页面样式调整 |
| `python-backend-ai-engineering` | “排查 FastAPI async 接口阻塞” | 纯 Java MyBatis 查询 |
| `vue-frontend-engineering` | “修复 Vue 路由切换后状态丢失” | 纯数据库索引分析 |
| `data-middleware-ai-infrastructure` | “分析 Redis 热点 Key 和缓存击穿” | 普通 Java 空指针说明 |
| `engineering-quality-delivery` | “修改后测试、六维复审并本地提交” | 只解释一个技术概念 |
| `technical-document-writing` | “编写正式架构设计文档” | 只改一条 Commit 信息 |
| `long-running-task-memory` | “这个任务跨多天，维护计划和交接” | 当前会话一次完成的小修复 |

## 二、推荐组合

| 任务 | 推荐组合 |
|---|---|
| Java Bug 修复 | Java + 质量交付 |
| Java + Redis/MQ 修复 | Java + 数据基础设施 + 质量交付 |
| Python AI Worker 故障 | Python + 数据基础设施；修改时再加质量交付 |
| Vue 与后端 SSE 全链路修复 | Vue + Java/Python + 数据基础设施 + 质量交付 |
| 基于代码写架构文档 | 文档 + 实际技术栈对应 Skill |
| 修改代码并更新正式方案 | 技术栈 + 质量交付 + 文档 |
| 跨会话大型改造 | 技术栈 + 质量交付 + 长期任务记忆；需要正式文档时再加文档 |
| 生产部署手册 | 文档 + 数据基础设施 + 质量交付 |

## 三、文档 Skill 触发测试

### 应隐式触发

1. 根据当前仓库写一份系统架构设计文档。
2. 把这份 Markdown 技术方案全面重构，保留业务口径。
3. 输出数据库表结构与索引设计文档。
4. 根据日志和代码写故障分析报告。
5. 整理成适合给领导讨论的正式项目报告。
6. 编写部署、灰度和回滚操作手册。
7. 写一份 API 接口设计和错误码说明。

### 通常不应单独触发

1. 给这个 Java 方法补一行注释。
2. 把 Commit 信息改成中文。
3. 只更新 CHANGELOG 中的一个条目。
4. 解释什么是 Redis 缓存击穿。
5. 执行 `npm run build` 并告诉我结果。

### 与其他 Skill 组合触发

1. “基于 Spring Boot 代码写接口设计文档”应组合文档 + Java。
2. “修改接口并更新技术文档、本地提交”应组合文档 + Java + 质量交付。
3. “根据 Celery Worker 故障写复盘”应组合文档 + Python + 数据基础设施。
4. “跨三阶段实施并维护进度和正式方案”应区分长期任务记忆与正式文档两个 Skill。
