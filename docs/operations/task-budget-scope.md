# 同一聊天内的任务预算

English: [Task budgets within a chat](task-budget-scope.en.md)

预算属于具有独立目标和验收边界的逻辑任务。一个 Desktop 聊天可以承载多个任务；聊天号只用于宿主来源绑定。Reviewer、Worker、Explorer 共享各自任务的根预算，追加额度仍绑定原根、工作项、角色和档位。

## 识别与恢复

主协调者按独立目标识别任务，无须用户反复说“新任务”。纠正、补充约束、修复、重试、拆分、改名和自动 Goal 续跑沿用原任务。含糊时继续原任务。语义识别是主协调者的策略责任，脚本不声称能够证明目标是否独立。

首次委派前或识别到目标切换时，使用 Task Envelope 的稳定 task_id 登记范围。保存返回的 task_scope 与账本路径到当前任务检查点。恢复时先读这些固定引用，不从聊天当前选择猜测旧工作的归属。

以下是已安装运行时的内部管理命令；源码开发入口为 scripts/cp-runtime.py。命令不启动模型、不授予文件或 Git 权限：

~~~text
cp-runtime.py task-scope-origins --session-id <native-session> --repo-path <repo>
cp-runtime.py task-scope-select --session-id <native-session> --repo-path <repo> --task-id <stable-task-id> --origin-ref <TO1-reference> --relation continue
cp-runtime.py task-scope-select --session-id <native-session> --repo-path <repo> --task-id <another-independent-task-id> --origin-ref <another-TO1-reference> --relation independent
cp-runtime.py task-scope-show --session-id <native-session> --repo-path <repo>
~~~

来源由原生父 Hook 绑定；只保存消息、文件身份和内容摘要，不复制 Prompt。带图片的真实用户文字可作为来源，自动 Goal 注入、工具输出和孤立批准不能创建新预算。同一个来源重放或改名复用原范围。新任务初始化要求匹配的已安装读取器，不能用尚未安装的源码迁移真实账户。

continue 优先复用明确的稳定 task_id，也可传 --task-scope 固定原任务；没有匹配名称时只沿用已有当前任务，不新建额度。resume 必须找到已登记任务。独立目标选用新的稳定 task_id；同一 task_id 永远复用原账本。跨聊天发现同一任务时需要保留原根的明确交接，本版不自动重建预算。

## 派发与回调

预览必须携带固定范围，不能在切换后重新读取当前任务来决定旧调用归属：

~~~text
cp-runtime.py task-scope-preview --session-id <native-session> --repo-path <repo> --task-scope <TS1-reference> --agent-type worker --task-name <local-name> --message-file <instructions-file>
~~~

执行脚本返回的 exact_tool_parameters。脚本生成有任务范围的子 Agent 名称，原生工具参数中不新增自报预算字段。PreTool 在会话锁下冻结调用归属，再由原账本原子预占；PostTool 按调用引用回查。子 Agent 创建恢复、Start/Stop、续跑和消息按原生头、回执及目标归属选择原根。任务 A 的迟到事件不会计入 B。

复审控制器初始化时传入该任务的 --delegation-ledger，之后所有命令验证原绑定。审批可以延迟恢复，但不能转到聊天后来选中的任务。不能用新任务额度支付旧任务的返工。

## 完成与迁移

~~~text
cp-runtime.py task-scope-complete --session-id <native-session> --repo-path <repo> --task-scope <TS1-reference>
~~~

仍有在途或未确认是否创建的调用时不能结算任务。完成检查与实际预占共用会话锁；完成后旧的未预占许可也不能启动调用，须先明确恢复原任务。迟到 Post/Stop 仍可结算。完成不删除账本，恢复不退还额度。原生调用已结算而宿主业务结论为 UNKNOWN 时分别报告；UNKNOWN 不自动意味着仍在运行或需要重启。

已有单任务 G6 聊天可先以 continue 登记整个旧根；不追溯拆账、清零或退款。旧路由指针按原始字节保留，预算历史保持原有版本和字节。发布新版本路由指针后，旧读取器明确拒绝新格式，不能回退到整条聊天预算。升级或回滚须保留能读新格式的运行时，不能直接降级覆盖已有新格式状态。

来源、身份或路由损坏只限制有关预算派发，其他已授权本地工作继续。首次新目标缺少原生来源时，继续原任务中可执行的工作并恢复来源；不要通过改账本、换聊天或伪造来源获得额度。

## 执行任务的追加与容量

复审追加只允许原定 Reviewer，不能转给 Worker 或 Explorer。执行任务使用独立的 `task_execution` 阶段，仍记在原任务根账本，绑定工作范围、角色和精确型号/强度。旧复审问题及批准原样回放；执行问题使用新的 question_version=2，逐项列出次数、尝试上限和规划单位，不冒充真实费用。

内部控制器复用 `review_controller.py`：以 `plan --phase post --review-stage task_execution --agents worker` 或 explorer 登记，传入实际 packet、purpose、model-profile 和 allowed-path。`allowance-quote --additional-dispatches N` 报价当前工作；多个已登记执行计划可用最多三项 `--work-count <work_id>=<count>` 合并报价。不同角色或档位不混用获批额度。派发必须提供具体 `--scope` 指令；包用于协调者核验，执行者只接收明确分配的输入，不接收包中的标准答案或其他样本结果。执行结果不进入 Reviewer 通过投影。

首次登记执行工作会追加 g6-budget-journal/3 记录，旧 /1、/2 前缀及费用不改写。必须先确认账户、缓存、调用端读取器一致。V3 上限为 8192 条记录、64 MiB，总量仍有界；每条新记录最多 16 KiB。报价和后续追加均为尚可执行的尝试预留记录/字节空间，包括未启动重试和未结算调用，空间不足时不产生不可执行的批准问题。旧版前缀仍按原限制和语义读取，不能降级读取新账本。

新来源选择在任务归属确认后才保存；另一个聊天已占用的 task_id 被拒绝后，可以用正确 ID 重试同一来源。已经创建根后发生发布中断则保持原选择，改名不能生成第二份预算。

## 验证入口

- [任务范围与晚到事件回归](../../tests/test_g6_task_scope.py)
- [原生来源](../../runtime/cp_runtime/g6_task_origin.py)
- [路由与迁移](../../runtime/cp_runtime/g6_task_scope.py)
- [门禁恢复原则](gate-recovery-policy.md)

隔离格式测试证明脚本合同；安装读回和真实 Desktop 多任务验收必须单独记录。

## 原生来源缺失的恢复

`task-scope-origins` 失败时返回结构化原因和下一步。不要要求用户反复发送“继续”修复内部登记。已有授权继续有效，来源恢复不授予新权限。

原生父 PreToolUse 通过既有上下文 Hook 登记宿主提供的转录定位，不保存提示正文。`task-scope-origins` 可据此自动恢复缺失来源；显式恢复也只消费已登记的宿主定位，调用方提供的文件不能建立来源资格。没有宿主定位时先修复 Hook 登记与信任，再执行普通工具调用，不要求用户重复输入。使用已安装且匹配的运行时：

```text
cp-runtime.py task-scope-recover-source --session-id <native-session> --repo-path <repo>
cp-runtime.py task-scope-origins --session-id <native-session> --repo-path <repo>
```

恢复共享原有文件身份、仓库、消息和摘要验证，记录为 `native_hook_locator_readback`，不伪造 Hook 事件、不清账、不替换损坏或冲突来源。重复恢复保持已有来源字节不变。长会话返回 `next_before_byte` 时，用 `task-scope-origins --before-byte <cursor>` 分段回读同一转录，每次最多 2 MB；没有受支持的真人消息仍保持未验证。控制回复不能创建独立预算，自动注入不能冒充真人消息。

`hooks_registration=MISSING/NOT_REGISTERED/UNREADABLE` 时同时按安装诊断修复 Hook 登记；`REGISTERED_UNVERIFIED` 只证明配置存在，不能声称真实执行或强制预算已生效。保留宿主信任要求，登记变化后按宿主提示审核，不手改信任记录。来源、预算、独立复审、安装和真实宿主验收分别报告。

迁移账户通过 Junction 指向实际目录时，内部安装器可显式使用实际 `CODEX_HOME` 与 `CP_ASSISTANT_AGENTS_HOME`。后者必须是当前账户既有 `.agents` 的同一物理目录；相对路径、其他目录、所选路径中的链接及受管子目录链接仍拒绝。不要改写用户身份环境变量，不要删除旧来源或账本消除冲突。

宿主提供的账户根联接路径仅在核实与当前 Codex Home 为同一物理目录后转换到规范位置；sessions 内部链接仍拒绝。观察失败只记录固定原因码与字段存在性，不保存命令、提示或路径正文。
