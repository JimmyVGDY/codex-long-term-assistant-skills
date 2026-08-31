# 安装包变更记录

## 2.0.0 - 2026-07-28

### 新增

- 新增 `technical-document-writing` Skill；
- 新增正式技术文档规则、文档类型 Playbook 和 12 个模板；
- 新增用户级、仓库级卸载脚本；
- 新增 `validate-package.py` 包结构校验脚本。

### 改进

- 全局 `AGENTS.md` 默认采用受管区块合并，保留已有规则；
- 验证脚本覆盖 7 个 Skills、`openai.yaml`、受管区块和文档模板；
- 明确正式文档、CHANGELOG 和 Agent 外部记忆的职责边界；
- 补充技术文档自动匹配和显式调用示例。

### 兼容

- 原有 6 个 Skill 名称保持不变；
- 原安装命令仍可继续使用；
- 重复安装会备份并更新同名 Skills。

## 1.0.0 - 2026-07-28

- 首次发布 Codex 跨项目长期技术助手 Skills 安装包。
