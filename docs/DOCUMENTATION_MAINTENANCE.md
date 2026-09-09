# 文档维护与事实校验

本文说明当前文档的修改入口、检查范围和发布交接。目录状态与语言来源由 [documentation.json](https://github.com/JimmyVGDY/codex-long-term-assistant-skills/blob/main/config/documentation.json) 管理。

以下维护命令在完整源码仓库的根目录运行。单语言发行包不包含 `locales/en` 和 `.github` 文档构建来源；包内文档可用于查阅，维护双语来源或重建站点时需使用完整源码。

## 修改入口

| 内容 | 修改来源 | 生成或核验的呈现 |
|---|---|---|
| 中文说明 | 根目录、docs、skills 下的中文源文件 | 中文站点与中文发行包 |
| 英文说明 | locales/en 下对应来源 | 同级 *.en.md、英文站点与英文发行包 |
| 当前包版本 | manifest.json；插件清单须匹配 | 带 cp-fact 标记的版本呈现 |
| Hook 注册 | hooks/hooks.json | 标记的入口名称和数量；具体用途仍需人工对照实现 |
| 格式版本 | 模板、运行时常量、结果 Schema | manifest 声明和标记的文档表格 |
| 状态归属 | manifest.json 的 authority_registry | 标记的权威来源引用 |

带 `Generated from` 标记的英文文件由构建生成。修改前先打开标记指定的来源；生成副本上的手工修改会使一致性检查失败。

## 日常修改流程

1. 读取相关源码、配置、调用方及现行说明，区分包版本、协议格式和历史引入版本。
2. 修改中文和英文权威源。新增 docs 文档时，在目录清单登记中文路径、英文来源和状态。
3. 执行下列检查；根据实际变更范围补充运行验证。

```text
python scripts/documentation.py sync
python scripts/documentation.py check
python scripts/check-links.py --strict
python scripts/localization-audit.py --strict
python scripts/build-docs-site.py
```

站点构建还应按现有文档工作流运行 MkDocs 严格构建。第二次 `sync` 应报告空的 `updated`，不得用重复生成掩盖源文件仍在变化。

## 当前、参考与历史

- `active`：当前操作和约束；进入默认站内搜索。
- `reference`：当前按需参考资料；进入默认站内搜索。
- `historical`：旧版本证据、指南和设计；站点增加历史提示并排除默认搜索。
- `generated`：从规范正文生成的兼容页，保留原章节锚点并排除默认搜索。
- 语言投影由 `english_projections` 单独登记，生成副本没有独立的事实所有权。

迁移前检查 GitHub 相对链接、站点 URL、关键锚点、英文投影和发行包引用。公开旧入口需要保留兼容页或跳转。目录清单中的 `aliases` 生成兼容副本；检查会拒绝副本漂移、循环映射和多个写入来源。旧入口与锚点由站点验收核对。

历史资料保留当时版本，不全仓替换旧数字。历史格式涉及已经停止的采集行为时，在页首标注历史用途并链接到现行协议。

## 检查范围与边界

自动检查覆盖登记完整性、生成副本漂移、必需的事实标记缺失、Hook 数量和列表、已知迁移边界错误、当前标题版本、格式声明和预算所有者一致性。它不执行运行时，也不读取项目任务状态。

自然语言中的适用条件、授权、安全限制和功能说明仍需对照实际实现复核。链接有效不等于描述正确；文档构建通过不等于宿主加载、门禁执行或业务验收通过。

## 发布证据与维护成本

### 发行源码边界

本地候选构建读取 Git 已跟踪文件的当前内容；新增源码、测试或英文覆盖文件必须先加入 Git。忽略文件和无关未跟踪文件不进入源码快照。暂存不等于提交，候选构建成功也不表示干净提交已经发布。

正式发行工作流先从干净提交捕获源码，再从同一快照构建双语包。需要无 Git 构建时，在完整 Git 源码根目录生成外部快照：

```text
python scripts/build-release.py snapshot --output <仓库外的新目录> --require-clean
```

本地候选允许省略 `--require-clean`。快照包含源码、英文来源及 `SOURCE_MANIFEST.json`；清单记录来源 HEAD、相对路径、大小、SHA-256 和整体内容摘要。随后进入快照目录，沿用 `build` 或 `reproducible` 命令。无清单、必要文件缺失、哈希不一致、路径冲突或链接会拒绝构建；未列入清单的附加文件不会参与英文覆盖。清单是内容核验输入，自带清单不能独立证明 Git 来源可信。

源码清单不会进入安装包、payload 或包内校验和；单语言安装包也不是可重建双语发行的源码快照。捕获限制为 10,000 个文件、单文件 32 MiB、合计 256 MiB；超限明确失败，需核实来源后调整范围或实现限制。源码捕获期间保持输入稳定；检测到输入或 Git 文件集变化时重试整个捕获。

发布记录必须区分候选验证和发布后读回。完成声明关联版本、完整提交、核验时间及精确工作流链接；不能只链接到可变化的工作流列表。公开状态需实际读回，离线文档检查不能证明工作流成功。

包内保留构建时已有的证据。后续发布、站点和账户加载结果追加到交付记录，不改写已经公开的标签或制品，也不把旧基线通过结果用于新修改。

优先沿用现有检查和构建入口。观察独立事实的手改次数、检查耗时、扫描量和历史缓存占用；有明确收益后再拆分模块，不增加常驻扫描、第二套项目索引或重复状态账本。

[文档中心](README.md) · [权威来源](AUTHORITY_REGISTRY.md) · [发行流程](releases/RELEASE_AUTOMATION.md)

## 仓库职责与运行入口

| 位置 | 职责与稳定入口 |
|---|---|
| docs/USER_GUIDE.md | 不带版本文件名的当前使用入口 |
| docs/operations/ | 配置、安装与恢复 |
| docs/architecture/ | 当前架构和边界 |
| docs/history/ 与 docs/releases/ | 历史设计和按版本保存的发行证据 |
| locales/en/ | 英文来源，其他语言呈现由构建生成 |
| hooks/ 与 runtime/ | 宿主适配与共享运行实现 |
| skills/、custom-agents/、global/ | Skill 发现、复审角色和全局规则 |
| scripts/cp-runtime.py | 项目绑定、能力索引和门禁命令 |
| scripts/package_manager.py | 插件安装、验证与恢复 |
| scripts/validate-package.py | 完整包验证入口 |
| tests/ 与模块内 tests/ | 跨模块回归和领域测试 |
| .agents/plugins/ 与 .codex-plugin/ | 固定插件发现入口和包元数据 |
| dist/ | 按版本和提交隔离的可重建产物 |

任务状态、证据归档与下载工具放在仓库外。整理历史资料时保留当前 Profile、索引和门禁绑定；先校验归档文件哈希及恢复映射，再清理原件。

当前包版本文字与验收报告链接使用 manifest 驱动的事实标记。与 manifest 版本相同的发行文档必须为 active，其他版本发行文档必须为 historical。发行索引链接到线上发布读回，不再手工保留易过期的“当前已发布版本”断言。
