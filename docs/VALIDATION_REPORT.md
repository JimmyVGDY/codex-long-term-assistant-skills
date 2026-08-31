# V4.1 安装包验证报告

## 验证对象

- 平台：Codex
- 版本：`4.1.0`
- 版本名称：执行确定性与独立上下文增强版
- 环境：Linux 容器，Python、Bash、Git 可用；PowerShell 和真实客户端运行不可用

## 已实际验证

- 9 个 Skills、Frontmatter、引用和平台元数据；
- 大 Reference 渐进分片和索引长度；
- 前端技术栈检测器原有测试；
- `execution_guard.py` 阶段、门禁、Git/差异指纹、未跟踪内容和 stale 证据测试；
- `review_packet.py` 统一审查包、未跟踪安全快照、packet hash 和结构化结果校验；
- `review_controller.py` 实施前/后轮次、深度、总预算、写入成功反证优先级、packet hash 和成本档位；
- `package_manager.py` dry-run、安装、重复升级、验证、doctor、旧路径迁移和恢复；
- 语义一致性扫描；
- Shell、Python、ZIP 和包内校验和完整性；
- 独立上下文委派协议、结构化结果 Schema 和文档完整性。

## 验证输出

```text
验证通过。
```

## 明确未验证项

- Windows PowerShell 5.1 / 7 实机包装脚本；
- 真实 Codex 客户端中的隐式 Skill 路由、自定义 Agent 发现和并行行为；
- 真实多子 Agent 并行性能、Token 与缓存数据；
- 运行时权限隔离仍必须按平台和父会话实际验证，不能由 TOML 声明替代。

## 结论

当前环境中的结构、工具、单元测试、安装恢复和语义验证通过；客户端运行时能力保留为本机验收项。
