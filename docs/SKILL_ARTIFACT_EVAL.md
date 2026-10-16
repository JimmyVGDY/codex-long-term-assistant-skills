# Skill 产物对照评测

English: [Artifact comparison](SKILL_ARTIFACT_EVAL.en.md)

scripts/skill-eval.py 在 Plugin 源码仓库中准备公开合成样例、记录实际产物并生成离线对照页。它复用既有复用案例、隐藏断言和 UX 指标合同，不调用模型，不把执行者自报或文件存在当成业务完成。

## 准备与执行

先冻结案例、允许修改、保护文件、断言、请求参数和权限边界。旧规则使用明确提交，候选规则默认使用当前工作区。目录必须为新的仓库外目录。

~~~text
python scripts/skill-eval.py prepare --suite <suite.json> --case <case-id> --baseline v7.16.2 --environment <environment.json> --output <new-external-directory>
python scripts/skill-eval.py prepare-reuse --case <existing-case-id> --baseline v7.16.2 --environment <environment.json> --allow-change <relative-file> --output <another-new-directory>
~~~

suite schema 为 skill-eval-suite/1，数据类型限定 public-synthetic。每个案例声明 task、skills、files、allowed_changes、artifacts 和 checks；样例准备入口拒绝覆盖规则、路径越界、链接和敏感材料。environment 固定 platform、runtime、requested_model、requested_effort、permissions_digest、cache_condition。权限摘要是已授权边界的记录，不授予系统权限。

准备生成两个独立目录、输入清单、规则快照和执行提示。执行者只读分配给自己的规则和任务资料，不读取对方产物、输入清单或隐藏答案。保持请求参数、环境和初始文件一致；执行中使用同一逻辑任务预算，不通过换聊天清零。授权任务的仓库外写入按[产物目录流程](operations/artifact-scope.md)恢复。

## 捕获、对照和查看

~~~text
python scripts/skill-eval.py verify-reuse --run <prepared-run-directory>
python scripts/skill-eval.py capture --input <run/input.json> --artifacts <run/workspace> --output <new-run-record.json>
python scripts/skill-eval.py compare --baseline <baseline-record.json> --candidate <candidate-record.json> --output <new-comparison.json>
python scripts/skill-eval.py render --comparison <comparison.json> --output <new-viewer.html>
~~~

capture 校验保护文件和实际产物，记录缺失、空文件、断言错误及未批准变更。verify-reuse 复用原隐藏 oracle，并将实际结果写入独立报告；原失败保留。比较前重验记录、源文件和条件，不能通过重算外层摘要掩盖伪造结果。新旧样例、环境、允许修改或断言不一致时不比较。

查看页转义所有文本，HTML 产物只展示源码。只对有界静态 PNG 提供内嵌预览；不加载远程图片，不执行脚本，不执行产物。单图最多 1 MiB、8192 边长和 8 Mi 像素；全页预览原始字节最多 4 MiB、图像最多 16 Mi 像素。其他格式或超限图片保留产物记录并提示预览限制。

## 可重复的公开合成案例

`scripts/quality-fixtures.py --output <external-suite.json>` 构造 12 个案例：三类完整/缺失文档、三类前端页面、六类 MCP 工具任务。用现有 `skill-eval.py prepare --suite <external-suite.json> --case <case-id> --baseline v7.16.2 --environment <environment.json> --output <external-run>` 冻结新旧规则和输入；读者及工具任务的标准答案留在评估输入，不发送给执行者。原生回答须原样保存后再核验，不能由协调者补写正确答案。

前端样例需在 360×800 与 1280×900 实际渲染，检查任务完成、内容层级、设计系统一致性、可读性、焦点、溢出、适用状态及减少动效；机械检查不能替代这一步。恢复文档及局部设计扩展按计划各版本重复三次；MCP 分页和权限案例各重复三次。

MCP 样例使用有界本地 JSON-RPC 子集，固定参考 [2025-11-25 Tools 合同](https://modelcontextprotocol.io/specification/2025-11-25/server/tools)，不连接真实服务，也不冒充完整协议或 Desktop 原生 MCP 连接器验收。合成写角色仅供单元测试构造，执行入口固定只读身份；实际工具输出和标准答案分别保存。

## 人工反馈与证据等级

~~~text
python scripts/skill-eval.py feedback-template --comparison <comparison.json> --output <new-feedback.json>
python scripts/skill-eval.py record-feedback --comparison <comparison.json> --feedback <filled-feedback.json> --output <new-feedback-record.json>
python scripts/skill-eval.py render --comparison <comparison.json> --feedback <feedback-record.json> --output <new-reviewed-viewer.html>
~~~

反馈必须引用真实产物，允许平局、证据不足和不适用。记录校验不证明评估者身份或盲评隔离。缺指标保留 UNKNOWN；机械检查、独立行为结果和收益结论分开报告。没有可靠独立样本时不宣称统计提升，也不自动改 Skill、路由策略或生产代码。

工具测试中的合成宿主报告和协调者制作的演示只证明合同或查看页行为，不能冒充独立模型对照。旧版本失败、缺失审计回调、未执行的宿主检查必须保留在各自证据层。

验证入口：[工具回归](../tests/test_skill_eval.py)、[规则快照与隔离目录](../tests/test_skill_fixture.py)、[反馈及复用断言](../tests/test_skill_review.py)。
