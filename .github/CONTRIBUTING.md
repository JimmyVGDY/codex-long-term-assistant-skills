# 贡献指南

English: [CONTRIBUTING.en.md](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/blob/main/.github/CONTRIBUTING.en.md)

感谢参与 Codex 跨项目长期技术助手。改动应保持安全边界、双语一致性与可回滚性。

## 开始前

1. 先搜索现有 Issue 与 Pull Request，避免重复工作。
2. 缺陷修复应提供最小复现、实际结果、预期结果与环境信息。
3. 行为变化较大的方案宜先建立 Issue，明确范围、兼容性和验证口径。
4. 漏洞或敏感信息不得进入公开 Issue，处理方式见 [安全策略](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/blob/main/.github/SECURITY.md)。

## 开发约定

- 从 `main` 建立短期分支，推荐前缀：`feat/`、`fix/`、`docs/`、`test/`、`ci/`。
- 保持最小充分改动，不夹带无关重构、依赖升级或格式化。
- 自然语言资料提供独立中文、英文版本；代码注释与 Docstring 使用整齐的中英配对格式。
- Reviewer TOML 不写死模型或推理强度。
- 不削弱 `execution_authorization=NONE`、Terra High 自动上限、项目隔离、哈希链与隐私边界。
- 新增运行时文件时同步更新对应测试、英文覆盖与发行构建门禁。

## 提交格式

提交信息采用：

```text
<类型> | <中文说明>
```

常用类型：`feat`、`fix`、`docs`、`test`、`ci`、`refactor`、`chore`。每个提交保持单一职责并可独立回滚。

示例：

```text
docs | 完善中英文安装说明
test | 增加发行包路径边界验证
```

## 本地验证

```powershell
python scripts\localization-audit.py --strict
python scripts\check-links.py --strict
python scripts\validate-package.py
```

链接检查覆盖所有受版本控制的 Markdown 路径、同仓库 URL 与标题锚点；外部链接由定时工作流补充探测。涉及发行构建时，再执行两个语言包的可复现构建与校验。无法完成的检查应在 Pull Request 中明确标记，并说明剩余风险。

## Pull Request

Pull Request 应包含：

- 改动目的与边界；
- 关键实现与兼容性影响；
- 已执行的命令和实际结果；
- 未验证项、风险与回滚方式；
- 文档及中英文同步状态。

合并、发布和部署是不同动作。Pull Request 获得认可，不等于自动获得发布或环境操作权限。
