# V7.4.4 验证报告

状态：本地 package-only 验证通过；远端提交、标签、CI、Draft 和公开发布尚未发生。V7.4.4 未执行真实账号安装。

## 本地验证

- `python scripts/validate-package.py`：237 项包测试与 6 项运行时测试通过，证据范围为 package-only；验证运行时为 Python 3.13.15，最低版本保持 Python 3.11。
- `tests.test_release_automation`：10 项通过；修复后连同两个英文包边界用例共 12 项定向测试通过。
- 严格本地化审计：778 个跟踪文件、770 个文本文件、526 个文档、118 个代码文件、126 个结构化文件，0 个问题。
- 全仓库链接审计：524 个 Markdown 文件、596 个链接，0 个问题、0 个警告。
- 语义检查、`git diff --check` 和 Plugin payload 校验通过；payload 为 182 个文件，摘要为 `7c9932a088275f27724578035fca08c453bfb69e40426eb224551ce6717bd138`。
- Codex 兼容注册表覆盖 11 个冻结稳定版本；Windows/Ubuntu 远端矩阵仍由标签 CI 单独验证。

## 独立复审与历史回填

功能/业务与安全 Reviewer 首轮均为 0 个 finding；交付 Reviewer 提出的历史证据索引和失败恢复手册缺口已集中修复并在第二轮确认，当前无剩余代码 finding。复审隔离等级为逻辑只读，不是系统只读；运行时模型身份未暴露，因此仅记录批准档位，不声称实际模型已核验。

v7.3.0、v7.4.0、v7.4.1、v7.4.2、v7.4.3 已从精确泛化标题更新为各自主题并逐个读回；v7.2.0 及更早未改。五次 before/after 校验确认 `body_sha256`、assets、draft、prerelease、published_at 不变，详见 [`HISTORICAL_RELEASE_BACKFILL.json`](HISTORICAL_RELEASE_BACKFILL.json)。

## 远端待验证范围

- `main` 推送与远端提交读回；
- annotated `v7.4.4` 标签及其 peeled commit；
- GitHub Actions Windows/Ubuntu 矩阵、来源证明和 Draft-only 行为；
- 六个 Draft 资产的下载、摘要和候选包复核；
- 公开 Release 的标题、状态、正文和资产读回。

不得把本地 package-only 结果解释为 CI、远端资产、公开 Release 或真实账号安装已经完成。
