# V7.4.4 发行说明

版本：7.4.4
主题：版本化发行标题与历史标题回填

## 发行标题

GitHub Release 标题由 `manifest.json.release_name` 与 `locales/en/manifest-localization.json.release_name` 组合生成：

- 中文：`版本化发行标题与历史标题回填`
- English：`Versioned Release titles and historical title backfill`

标题元数据必须是非空字符串，并拒绝空白、前后空格、控制或格式字符、超长值以及泛化占位标题；任一约束失败均失败关闭。工作流通过 job output 再经环境变量传递标题，避免在 shell 中直接插值表达式。

长度上限为：中文 30 个 code points、英文 80 个 code points、组合标题 125 个 code points 或 200 个 UTF-8 bytes；并拒绝 Unicode `Cc`、`Cf`、`Cs` 类别字符。

## 发布边界

- 工作流只创建供维护者检查的 Draft Release，不自动公开发布。
- 目标标签已有 Release 时跳过创建，不覆盖既有 Release 或资产。
- 中文与英文资产分别进行可复现构建；校验和、构建见证和 GitHub provenance 一并保留，用途彼此独立。
- Codex CLI 0.153.2 兼容边界保持不变，不扩展未来版、预发布版或窗口外版本。

## 历史标题回填

历史 Release 标题回填是独立的线上元数据操作，不属于本地构建或 Draft-only 工作流。v7.3.0、v7.4.0、v7.4.1、v7.4.2、v7.4.3 均已完成回填并逐个线上读回；v7.2.0 及更早版本未修改。五次 before/after 校验均确认 `body_sha256`、assets、draft、prerelease、published_at 不变；逐版本 Release ID、前后标题和保留字段摘要见 [`HISTORICAL_RELEASE_BACKFILL.json`](HISTORICAL_RELEASE_BACKFILL.json)。

## 证据状态

V7.4.4 的本地 package-only 验证和逻辑只读独立复审已通过；CI、远端标签、Draft 资产与公开 Release 仍需后续线上读回，且本版本未执行真实账号安装。历史标题回填已由线上读回证据确认完成。
