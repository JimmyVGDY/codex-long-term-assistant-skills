# v4.0 安装包验证报告

## 验证对象

- 平台：Codex
- 版本：`4.0.0`
- 基线：v3.3 Reviewer 隔离修正版
- 日期：2026-07-31
- 环境：Linux 容器，Python、Bash、Git 可用；PowerShell 和真实客户端运行不可用

## 变更范围

- `vue-frontend-engineering` 直接改名为 `frontend-engineering`；
- 通用前端覆盖主要现代框架、传统页面、静态 HTML/JSP、Hybrid Web 与 Renderer 边界；
- 11 份前端参考规则、3 个模板、只读有界技术栈检测器和 12 个检测器自测；
- 检测器增加 Workspace、源码签名、无 package.json、Fullstack Web、Hybrid Web 和纯 Node.js 负向识别；
- 用户级与仓库级升级自动备份/清理旧 Skill；
- 路由回归覆盖多框架、微前端、SSR 安全、传统/静态页面、Hybrid Web 和桌面主进程排除；
- 分发包禁止残留 `__pycache__` 与 `.pyc`；
- 保留 v3.3 Reviewer 运行时隔离修正。

## 自动验证结果

结果：**通过**

```text
验证通过。
```

已实际执行：

- 9 个 Skill 的名称、Frontmatter、目录和相对引用检查；
- 11 份前端 references 与 3 个模板完整性检查；
- 检测器和测试脚本语法检查；
- 12 个检测器单元测试；
- 路由用例结构、旧名称清理和纯 Node/桌面主进程负向场景检查；
- Shell 脚本语法；
- 隔离 HOME 中的用户级首次安装、重复升级、验证和卸载；
- 仓库级旧 Skill 清理和新 Skill 安装；
- 第三方 Skill 保留；
- Python 缓存文件零残留；
- ZIP 完整性和包内 SHA-256 清单。

## 明确未验证项

- 当前环境未执行 Windows PowerShell 5.1 / 7 实机安装；
- 未在真实 Codex 客户端执行隐式 Skill 自动触发；
- 最终应在本机执行验证脚本，重启客户端并检查 `/skills`。
