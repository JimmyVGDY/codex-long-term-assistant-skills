# 项目能力索引

能力索引保存项目中可复用入口的定位与核验线索。源码、配置和测试仍是技术事实；索引不授予执行权限，也不自动晋升为稳定项目记忆。

## 当前实现范围

`runtime/cp_runtime/capability_store.py`提供存储API；`capability_index.py`提供有界扫描、候选查询、登记迁移和生命周期更新；`capability_cli.py`将这些操作接入既有项目运行工具。代码已在本地实现，独立行为验收、成本对照及安装加载仍需单独证明。

构造`CapabilityStore(profile_path, repo_path, index_root=None)`时，使用既有Project Profile和Project State校验绑定。显式索引目录必须是绝对的仓库外路径；默认目录为Profile同级的`capability-index/<worktree_id>`。工作区ID是规范化绝对根路径的全长SHA-256。不同worktree使用各自Profile，不自动沿用主工作区的未提交事实。

## 存储契约

当前格式版本为1。索引包含`schema_version`、`revision`、`identity`、`baseline`、`coverage`、`entries`、`recovery_source`及`integrity`，拒绝未知或重复字段。

| 内容 | 含义 |
|---|---|
| identity | 项目ID、仓库指纹、Profile位置与绑定摘要、工作区根及ID、索引目录 |
| baseline | HEAD、分支及限定范围文件的完整SHA-256；不使用全仓快照作为热路径 |
| coverage | 范围、完成标记、续扫定位和枚举限制原因；空索引为UNSCANNED |
| entries | 稳定ID、类型、相对路径、符号、简短职责、关键词、边界、引用及核验范围；每条独立保存observed_baseline与observed_at，人工登记说明另有recorded_at |
| lifecycle | candidate、active、deprecated、removed |
| freshness | matched、recheck、stale、unknown；matched不表示业务适用性已通过 |

每份序列化索引最多8 MiB和2,000条能力；每条摘要最多500字符；调用方、测试和上下文引用各最多5项。扫描每批最多枚举2,000个目录项、执行128次正文读取、读取合计2 MiB，单文件最多128 KiB。正文预算包含结束时的完整二次核对；通常最多首次读取64个不同文件。相关构建配置的存在性探测另有缓存与硬上限，不能沿深目录无限检查。

所有路径在解析前逐层拒绝符号链接和Windows reparse/junction。条目路径不接受绝对路径、盘符、上级跳转、控制字符或秘密目录。摘要和值接受敏感模式检查，不保存完整源代码、配置值、请求和异常正文。模式识别不能证明识别了所有编码秘密。

## 更新与恢复

1. `commit(payload, expected_revision=None)`仅在当前和上一快照都不存在时初始化，revision为0。
2. 后续更新必须提供精确revision。持有现有`OwnerTokenLock`后重新校验身份并读取当前文件。相同事实返回原快照，不写文件或增加revision。
3. 有变化时先验证候选，再原子发布旧内容至`index.previous.json`并读回，随后发布`index.json`并读回。前一步失败不发布当前候选。
4. 当前文件发布或发布后核对失败时返回`COMMIT_UNCERTAIN`。调用者须重读实际文件，不得直接重复提交或声称已回滚。
5. `recover(expected_current_sha256)`需当前原始字节的SHA-256；文件缺失时使用`MISSING`。恢复源必须通过格式、身份、完整性及版本顺序验证。
6. 恢复前将现有原始文件保存为同目录的`index.recovery-<sha256>.bin`；不会将内容写入普通诊断。保留上一有效快照，恢复后版本至少为其revision加2。旧恢复令牌再次使用冲突；重读后相同恢复事实为无写入操作。
7. 当前文件明确属于其他身份或未知格式时拒绝恢复。应另行检查绑定或采用有备份的迁移流程，不能用恢复掩盖版本不兼容。

此协议支持同账户合作式工具并发，不宣称抵抗拥有操作系统特权的恶意进程。原子替换保证单个文件发布边界；两份文件不是跨文件数据库事务。进程终止前后的结果由有效当前快照、上一快照和明确读回决定。

## 扫描与开发使用

源码入口为`python scripts/cp-runtime.py`，安装后使用已验证安装位置的`cp-runtime.py`。各命令均需`--profile`与`--repo-path`，可选择绝对的`--index-root`。

| 命令 | 用途与关键参数 |
|---|---|
| capability-init | 建立明确未扫描的空索引；已有快照时拒绝覆盖 |
| capability-scan | `--scope`可重复指定文件或目录；省略时从仓库根有界发现；`--resume`继续已保存的待处理清单 |
| capability-query | `--term`检索路径、符号、已登记职责与关键词；默认5项，`--limit`最多20项；`--include-inactive`明确查询弃用/移除条目 |
| capability-invalidate | `--changed-path`可重复；按引用和模块范围标记待复核；需`--expected-revision`，依赖图不完整时保守扩大 |
| capability-register | `--entry`读取一条完整且通过schema校验的JSON；需`--expected-revision`；相同ID的新定位是明确迁移映射，重读文件与引用后登记 |
| capability-lifecycle | `--entry-id`、`--lifecycle`和`--reason`明确修改状态；需`--expected-revision`；确认移除时拒绝仍存在的文件 |
| capability-validate | 校验存储格式、身份和完整性，返回有限摘要；缺失快照明确报INDEX_MISSING，不创建索引、不批准语义复用 |
| capability-recover | 使用`--expected-current-sha256`显式恢复上一有效快照 |

Python使用AST识别顶层公开定义，以及静态`__all__`声明的入口。JavaScript/TypeScript使用有边界的文本识别覆盖常见ESM和CommonJS导出；仅是候选定位，不能视为完整语法分析或调用图。动态导出、其他语言以及不能读取的内容保留限制；可经实际源码核实后显式登记。

自动扫描不从注释、docstring或配置值生成职责摘要。默认跳过依赖、构建产物及常见生成目录；不执行项目代码。安全的请求方输入路径可以出现在覆盖范围，命中敏感正文时不保存正文、摘要或新文件指纹，仅记录限制原因。

正文预算用完时，`coverage.cursor.pending`保存有限待处理路径；命令仅输出剩余数量。恢复前检查Git基线。目录本身超出枚举上限时记录`DIRECTORY_BUDGET`：已发现路径可以继续处理，未枚举尾部必须通过更窄的明确范围检查，不能靠反复读取同一目录前缀冒充完整续扫。`complete`只覆盖声明的识别策略及范围，不表示发现了所有项目能力。

查询重新读取候选文件、已登记引用和邻近构建配置；文件相同仅证明观察内容匹配。查询不写索引，源码或配置变化返回stale/recheck和原因；索引缺失、无匹配或覆盖不足时需返回源码检索。查询始终返回`semantic_reuse_approved=false`。

缺失查询结果的`maintenance`说明首次已授权的非简单接管或共享接口变更应执行限定初扫；无适用触发时仍可源码检索。失效结果明确`INVALIDATED_NOT_UPDATED`及下一步限定扫描，避免把失效当成更新完成。这些提示不自动执行命令，也不增加授权。

扫描已变化源码后，当前文件、已登记调用/测试引用及构建上下文匹配时可标为matched；业务适用性仍未批准，旧语义核验依据在源码、上下文或引用失效后清空。未匹配的调用/测试引用保持recheck。对相同事实再次扫描不会仅为切换新鲜度而增加revision。

普通读取、显式登记和恢复头解析均拒绝重复JSON字段；恢复也拒绝布尔值伪装的格式版本。这些拒绝不改写当前、上一快照或生成恢复备份；明确损坏数据的合法恢复路径仍按前述协议执行。

开发完成后先使显式变更路径关联的条目失效，再扫描已核实的变更源文件及查询后实际采用的过期候选源文件；后者即使未改动也需更新定位指纹。无关未使用条目可保持待核验；刷新指纹不批准业务适用性。需要语义说明或迁移时使用显式登记。同一条能力的观察基线独立保留，切换分支后不能因重复扫描而将另一分支的能力误删。无事实变化的扫描、登记和失效不会反复增加revision。

同一文件与符号的公开声明类别变化时，重扫同步function/class/component/module分类并失效旧语义依据，保留条目ID、人工摘要、边界和引用。显式登记的service/adapter是业务职责分类，扫描不以语法类别覆盖；文件变化仍使其旧核验依据失效。

重新构建损坏且无有效上一快照的索引时，显式指定新的仓库外目录，从授权范围重新扫描并核验；保留原目录，将新位置写入本任务外部交接。不得删除旧索引或修改Profile来暗中切换绑定。

## 验证入口

项目可显式启用流程门禁，使用`capability-gate-enable/status/disable`管理；开发使用`capability-task-prepare/finish/check`。默认关闭，不改变未启用项目的观察与预算流程。起点由真实宿主建立，不能从CLI补造；PASS证明当前流程证据有效，不批准语义复用。启用条件、精确revision、宿主身份、取消与状态限制见[完整操作流程](../skills/engineering-quality-delivery/references/capability-index-workflow.md#项目显式启用的流程门禁)。源码实现、包验证、安装加载和真实新任务验收须分别确认。

在源仓库根运行：

```text
python -m unittest discover -s runtime/tests -p "test_capability*.py" -v
```

测试覆盖身份、幂等、版本冲突、真实双进程竞争、进程终止后的锁释放、快照替换故障、显式恢复、体积限制、敏感字段、读取竞态及Windows目录联接。非Windows环境的目录联接专项会明确跳过。存储测试不证明首次扫描、语义复用、成本收益或插件加载。

默认遍历跳过`.agents`和`.codex`工具目录，避免将助手工具误认为业务能力；需要维护这些工具本身时，可以显式指定其中的源文件范围。

默认无需传入`--index-root`。保留的`<Profile目录>/capability-index`容器不能作为独立快照目录，误用返回`INDEX_ROOT_IS_CONTAINER_OMIT_OVERRIDE`且不写文件；明确指定工作区快照目录或其他已授权自定义目录仍受支持。

冷索引的免初扫例外限于单个既有文件。跨文件准备或新增文件走有界初扫；扩大免初扫范围前已有准备内容必须未变。当前核验会将不合格的旧无索引PASS降为BLOCKED并记录INITIAL_SCAN_NOT_PROVEN，合规单文件回执继续有效。此条件不批准单文件的业务语义，未启用项目保持原行为。

相关文档：[能力索引](CAPABILITY_INDEX.md) · [验收规程](COMPONENT_REUSE_ACCEPTANCE.md) · [V7.6.0 验证报告](releases/v7.6.0/VALIDATION_REPORT.md)。
