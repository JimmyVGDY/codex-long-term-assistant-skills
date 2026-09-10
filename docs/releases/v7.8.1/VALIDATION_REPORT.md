# V7.8.1 验收记录

本记录分开报告源码候选、公开发行与现用账户生效。最终数字在发布提交稳定后读回，不以计划或历史版本代替。

| 边界 | 当前合同 |
|---|---|
| C01-C25 | 静态注册表必须恰好 25 项，Manifest、Hook、CLI 新入口存在未归类项时阻止“全部覆盖”声明，不阻断普通对话。 |
| AUTO 与权限 | OFF/最高档位/前提/风险分别计算；`authorization=false`、`action_status=NOT_AUTHORIZED` 固定。 |
| 首次引导 | 只有读回确认的 `ACCEPTED_PERSISTED` 能排队全扫；未答、拒绝、保存失败继续 BASIC。 |
| 扫描任务 | offer -> scan -> index 锁顺序、lease generation、cancel epoch、索引提交先于游标、晚到 fencing 和三次接管上限。 |
| 安装与自救 | Python 3.11+ 真实探测、分功能 doctor、只读 inventory、规范 recover、无 state 零删除预览和非 Git BASIC 指南。 |
| AGENTS 归属 | 只核对唯一受管区块；标记外自有文本不算漂移，区块变化/重复/缺失与路径越界继续失败关闭。 |
| 复审 | U02-U13、UX01-UX40、M01-M12、T25-T28 有逐项合同和可发现测试；实施后独立复审另行读回。 |

## V7.8.1 补丁候选证据

- V7.8.0 公开安装后复现：verify/doctor/Plugin 读回均 PASS，但旧 inventory 只把 AGENTS 误报为 `DRIFT`；受管区块重建哈希与源区块精确一致。
- 修复后 5 项定向回归 PASS，现用 V7.8.0 状态通过新 inventory 读回为 13/13 `MANAGED`；新增测试覆盖标记外自有编辑不漂移、受管内容编辑为 `DRIFT`。
- `python scripts/validate-package.py` 完整重跑 PASS：423 项 package + 205 项 runtime，Python 3.13.15；文档、本地化、链接、语义、隐私、路由、委派、payload 和工作区副作用门禁均 PASS。
- Windows 锁文件并发初始化压力测试连续 30 次 PASS；文档、本地化、链接、语义、隐私、路由、委派和 payload 门禁 PASS。
- disabled/unconfigured 文件门禁 50 次真实进程：p50 82.22 ms、p95 87.35 ms、p99/max 88.46 ms，满足 p95 ≤ 300 ms、p99 ≤ 1 s。
- R3 实施后状态/并发与测试/交付 Reviewer 在合并前刷新包 `f22009…a01402` 上 PASS。拒绝取消补偿与 C20 假入口两个 HIGH 已修复；V7.7.1 兼容补丁也有其独立复审与发布证据。合并后的组合基线执行了上述完整本地重验，但未把它表述成一次新的独立 Reviewer 复审。
- V7.8.1 是安装证据投影的单点补丁，已执行定向与完整本地重验；没有把 V7.8.0 的独立 Reviewer 结论冒充为本补丁新增的一轮独立复审。
- 公开 CI、Release、匿名下载、账户安装、重启和新任务加载尚未在本记录中证明。

## 状态分离

- `RELEASE_COMPLETE`：需要提交、PR 合并、标签、发布工作流、公开资产、匿名下载和隔离安装全部读回。
- `INCIDENT_EFFECTIVE`：需要现用账户安装、必要重启、新任务实际加载以及原项目消息验收；与 `RELEASE_COMPLETE` 分别确认。
- 本文进入源码时仍是候选记录；没有后续证据的项目不得把上述状态写成已完成。
