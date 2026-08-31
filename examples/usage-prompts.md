# Codex Skills 使用示例

## Java 本地修复并提交

```text
使用 $java-backend-engineering、$data-middleware-ai-infrastructure
和 $engineering-quality-delivery。

全面阅读相关调用链后修复当前接口问题，保留原有业务逻辑，
执行相关后端定向测试和六维复审，更新项目既有 CHANGELOG，
创建本地提交但不要推送。
```

## 编写系统架构设计文档

```text
使用 $technical-document-writing、$java-backend-engineering、
$python-backend-ai-engineering 和 $data-middleware-ai-infrastructure。

基于当前仓库实际代码、配置和部署文件编写系统架构设计文档。
不得编造未实现的组件；区分已确认事实、推断和未验证项。
包含系统边界、服务职责、数据所有权、接口、缓存、MQ、权限、
部署、监控、容量、风险和演进路线。
```

## 基于现有文档全面重构

```text
使用 $technical-document-writing。

完整阅读现有 Markdown 文档，在不改变已确认业务口径的前提下全面重构：
去除重复内容，修正标题层级，统一术语，补充范围、非目标、风险、
验证和回滚。材料没有支持的内容标记为待确认，不要自行补成事实。
```

## 修改代码并同步正式技术方案

```text
使用 $java-backend-engineering、$engineering-quality-delivery
和 $technical-document-writing。

完成当前功能修复和定向验证后，更新项目已有技术方案与 CHANGELOG。
正式文档只记录实际实现和实际验证，不把计划或未验证项写成已完成。
本地提交但不要推送。
```

## Python AI 任务只读排查并输出报告

```text
使用 $python-backend-ai-engineering、$data-middleware-ai-infrastructure
和 $technical-document-writing。

只读排查当前 GPU Worker 间歇停摆问题，基于代码、日志、配置和资源数据
输出故障分析报告，列出证据等级、候选原因、验证步骤、止血方案、
正式方案和未验证项，不修改文件。
```

## Vue 状态与 SSE 修复

```text
使用 $vue-frontend-engineering、$java-backend-engineering
和 $engineering-quality-delivery。

排查页面切换后 SSE 状态丢失及重复消息问题，检查前后端完整链路，
完成最小修改、前端生产构建和相关后端定向验证。
```

## 跨会话大型任务

```text
使用 $long-running-task-memory、$engineering-quality-delivery
以及当前技术栈对应技能。

先建立当前任务卡、计划和进度记录；外部记忆不得进入项目仓库。
需要给团队交付正式技术方案时，另使用 $technical-document-writing。
按阶段完成修改、验证、复审和本地提交，不推送。
```
