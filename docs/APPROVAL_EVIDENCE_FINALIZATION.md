# Approval、Evidence 与 Finalization

## 1. 三类对象

| 对象 | 回答的问题 | 不回答的问题 |
|---|---|---|
| Approval | 当前动作是否获得明确、仍有效的授权 | 动作是否执行成功 |
| Evidence | 某项验证、Review 或读回观察到了什么 | 是否允许执行其他动作 |
| Finalization | 最终声明是否被当前事实支持 | 不执行动作，也不替代验收 |

## 2. Approval

Approval 至少绑定：

- Approval ID；
- Project ID；
- Task ID；
- 操作；
- `local/nonproduction/production` 环境；
- 当前仓库基线 SHA-256；
- 签发时间和绝对过期时间；
- 一次性消费状态。

### 2.1 记录明确授权

上层已经获得已取得明确授权后：

```bash
python3 scripts/cp-runtime.py approval-issue \
  --output /external/approvals/APR-001.json \
  --approval-id APR-001 \
  --profile /external/project/project-profile.json \
  --task-id TASK-001 \
  --operation commit \
  --environment local \
  --repo-path /path/to/repo \
  --ttl-minutes 30 \
  --approved-by user
```

该记录是可审计完整性记录，不是数字签名，也不能防御拥有同等文件写权限的恶意修改者。

### 2.2 动作前消费

```bash
python3 skills/engineering-quality-delivery/scripts/execution_guard.py authorize-action \
  --state-dir /external/task/TASK-001 \
  --action committed \
  --approval /external/approvals/APR-001.json
```

动作前如仓库代码变化，Approval 会因基线不一致而失败。

### 2.3 动作后读回

```bash
python3 skills/engineering-quality-delivery/scripts/execution_guard.py record-action \
  --state-dir /external/task/TASK-001 \
  --action committed \
  --status success \
  --evidence "git rev-parse HEAD = ..."
```

`record-action` 不执行 Commit，只记录外部动作完成后的实际读回。

## 3. Evidence Freshness

```bash
python3 scripts/cp-runtime.py evidence-record \
  --output /external/evidence/EV-001.json \
  --evidence-id EV-001 \
  --profile /external/project/project-profile.json \
  --task-id TASK-001 \
  --repo-path /path/to/repo \
  --kind validation \
  --status valid \
  --source "mvn test" \
  --summary "定向测试通过"
```

代码、暂存区或未跟踪文件变化后，Evidence Freshness 返回 `STALE`，不能继续作为当前基线的验证结论。

## 4. Finalization Integrity

```bash
python3 skills/engineering-quality-delivery/scripts/execution_guard.py finalize \
  --state-dir /external/task/TASK-001 \
  --claim modified \
  --claim validated \
  --claim committed \
  --output-json /external/task/TASK-001/finalization.json \
  --output-markdown /external/task/TASK-001/finalization.md \
  --require-all
```

支持的声明：

```text
modified
validated
reviewed
committed
pushed
deployed
restarted
effective
```

任何声明缺少当前证据时，结果为 `BLOCKED`。其中：

- `committed` 通过任务初始 HEAD 与当前 HEAD 变化判断；
- `pushed` 只有动作读回或本地 upstream 引用支持，后者会明确保留“未联网读取远端”的限制；
- `deployed/restarted/effective` 必须有显式动作读回；
- 文本扫描和状态记录不能替代平台真实状态。
