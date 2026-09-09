# V7.5 受控演进操作手册

状态：`active`，适用于 V7.6.0。默认与显式策略统一为 `v7.4.3-default-1`。所有提案始终保持 `execution_authorization=NONE`。

## 1. 任务反馈

完成项目 Onboarding 后，`UserPromptSubmit` 在宿主提供完整身份时输出反馈绑定：`context_root/project_id/session_id/turn_id/task_id/cli_path`。工程任务把本来需要执行的验证交给下列入口；不要为了反馈另跑无意义的测试。以下占位值使用本次 Hook 的真实绑定，不能从最近一个任务猜取。

```text
python scripts/evolution.py validate-task --context-root CONTEXT --project-id PROJECT --session-id SESSION --turn-id TURN --task-id TASK -- python -m unittest tests.test_target
python scripts/evolution.py finalize-task --context-root CONTEXT --project-id PROJECT --session-id SESSION --turn-id TURN --task-id TASK --actor parent:TASK --outcome PASS --failure-category NONE --routing-deviation MATCHED --repair-rounds 0 --evidence feedback/validations/VAL_ID.json
```

`validate-task` 只保存命令摘要、退出码、时长、Git 提交和工作树指纹，不保存命令、输出、Prompt 或代码正文。命令失败或验证期间工作树变化时 CLI 返回非零。主协调 Agent 最终确认终态、失败分类、返修次数、路由判断；通过/失败计数来自引用的验证证据。返修前失败证据保留，最终报告引用当前相同工作树上的验证。

`PASS` 必须有有效通过证据；证据缺失时保留 `UNKNOWN`，不得解析自然语言回答猜成败。Stop 自动核验身份、报告哈希、证据和当前工作树并关联报告；原始 Hook 终态与来源字段保持原样，由观察器合并反馈。旧任务迟到的最终化报告也是有效增量。报告不可覆写，同内容重试幂等，冲突拒绝。

失败分类：`NONE/INPUT_CONTRACT/ROUTING/IMPLEMENTATION/VALIDATION/REVIEW/ENVIRONMENT/UNKNOWN`。路由判断：`MATCHED/MISSED/UNNECESSARY/WRONG_DOMAIN/UNKNOWN`。只有主协调者已确认的根因才能附加 `--root-cause-id ROOT --root-cause-confirmed`。

## 2. 先检查观察健康

```text
python scripts/evolution.py health --context-root CONTEXT --project-id PROJECT
python scripts/evolution.py run --context-root CONTEXT --project-id PROJECT --dry-run
```

`run` 和自动增量分析均先通过健康门禁。`observe` 是保留历史兼容的底层只读接口，不能把其输出当成健康门禁通过。

| 状态 | 含义和处理 |
| --- | --- |
| READY | 健康且有合格信号，可形成候选 |
| HEALTHY_NO_SIGNAL | 健康但未发现合格信号，保持安静 |
| INSUFFICIENT_DATA | 独立任务、窗口或所需覆盖不足，继续采集 |
| IDENTITY_UNAVAILABLE / IDENTITY_MISMATCH | 缺少有效绑定或项目/仓库不符，停止聚合 |
| DATA_DAMAGED | Profile、数据、引用或封印损坏，停止分析并保留证据 |
| SEAL_PENDING | 尚有待封印尾部，等待 worker 完成 |
| STALE_DATA | 默认最近记录超过 30 天，不能当成当前结论 |

健康报告列出策略摘要、身份、链完整性、生命周期、已知终态、Reviewer 归因和成本覆盖。信号按各自的证据门槛判断。不要通过重算历史哈希、跳过坏行或混入其他项目来解除门禁。

## 3. 有效增量与项目自动化

```text
python scripts/evolution.py incremental-run --context-root CONTEXT --project-id PROJECT
python scripts/evolution.py automation enable --context-root CONTEXT --project-id PROJECT
python scripts/evolution.py automation tick --context-root CONTEXT --project-id PROJECT
python scripts/evolution.py automation disable --context-root CONTEXT --project-id PROJECT
```

自动化默认关闭，显式启用只允许检查、聚合和候选生成，不包含实施权限。已启用项目由现有 SessionEnd 封印 worker 触发，不新增服务。默认至少 3 个新增独立任务、冷却 3600 秒；观察器原有样本和窗口门槛仍适用。`--milestone VERSION` 可显式触发里程碑分析；策略变化及迟到反馈/校准样本也被识别。

`NO_CHANGE/WAITING_FOR_TASKS/COOLDOWN` 保持安静。输入指纹包含策略、记录身份/哈希、反馈和校准数据；项目锁内先写不可变事务与快照、注册候选，再原子提交水位。无变化也复验已有输出。中断后重试复用事务，失败不消费水位。worker 分析失败保存 `evolution/automation-last-result.json` 中的 `RETRY_REQUIRED`；后续有效封印或手动 tick 可重试，同状态不重复通知。通知标志供调用方消费，运行时不发送外部消息。

## 4. 跨独立任务校准

```text
python scripts/evolution.py calibration-source --context-root CONTEXT --project-id PROJECT --ledger calibration/task-a-budget.jsonl --samples calibration/task-a-samples.jsonl
python scripts/evolution.py calibration-replay --context-root CONTEXT --project-id PROJECT
```

每个任务分别登记自己的账本与样本文件，路径必须位于同一项目上下文。每条样本验证所属已完成预算预留、批准档位、成本和主协调者最终化证据，然后按角色、职责、难度、风险、上下文分组。任务内部先聚合，任务之间等权；保留各档位独立任务数、保守区间和质量损害率。场景未知、样本不足或区间重叠时不建议改档。全局观察器与离线回放共用比较函数；旧 Reviewer 总体代理仅用于诊断，不能驱动新项目自动候选。

## 5. 假设、实施与收益

新提案 schema 2.0 固定基线快照/指标、改善方向和目标、质量底线、项目/仓库/场景范围，默认至少 5 个独立任务和 7 天观察窗口。基线与后续观察必须使用相同策略和不重叠的任务群，后续窗口必须晚于实施验证。结果属于观察证据，不是因果证明。

人工 `decide --decision accept|reject|defer` 必须带 `--proposal-id`、`--actor` 和至少十个字符的 `--rationale`。`ACCEPT` 只允许另建独立授权的实施任务；不会执行修改。实施任务沿正常 Task Envelope、审批、验证和复审流程推进。

```text
python scripts/evolution.py snapshot --context-root CONTEXT --project-id PROJECT --window-start START_ISO --window-end END_ISO
python scripts/evolution.py observe-benefit --context-root CONTEXT --project-id PROJECT --proposal-id PROPOSAL --actor parent:TASK --before BASELINE_PATH --before-hash BASELINE_HASH --after AFTER_PATH --after-hash AFTER_HASH
python scripts/evolution.py validate --context-root CONTEXT --project-id PROJECT
```

通过 `link-implementation` 登记任务与 Git 基线，`record-validation` 登记实施提交及 `validate-task` 产出的证据。`snapshot` 时间窗口为带时区的半开区间，before 必须使用提案冻结的基线快照引用。`observe-benefit` 登记时和生命周期读回时均重验引用与指标。

实施验证 `PASS` 与收益 `SUPPORTED/NOT_SUPPORTED/REGRESSED/INSUFFICIENT` 分开。`close --outcome PASS` 仅在最新收益 SUPPORTED 时合法；证据不足继续观察。取消记录明确的提案取消声明；回滚必须提供基线提交上干净工作树的验证证据。终态之后不得追加观察。旧 schema 保留原有哈希和生命周期，不伪造补齐新收益合同。

## 6. 从失败生成回归候选

已确认根因形成重复失败提案后，自动生成 `evolution/regression-candidates/` 下待审负向用例、路由正反例或前置校验候选，关联原报告和验证证据。候选只包含条件与预期，具体项目 fixture 必须在独立授权任务中实现。后续收益报告生成 `regression-followups/`，记录同类失败复发率和样本不足状态。跨项目推广继续单独审核；不会自动写业务测试、接受提案或修改规则。

每个项目/仓库/会话/轮次/任务只有一份不可变定稿；定稿后工作区变化必须在新轮次验证和收尾。经健康检查的信号变化可绕过新增任务与冷却门槛，损坏或不完整的生命周期仍被健康门禁拒绝。收益前后样本均排除实施任务。注册表验证会重放回归跟踪的候选来源、实施证据、独立任务与观察窗口。
