# 项目上下文与已有项目接管

## 1. 使用场景

以下情况建议先执行 Project Onboarding：

- 第一次进入陌生仓库；
- 同时维护多个相似项目；
- 项目跨会话或长期维护；
- 准备执行 Commit、Push、部署、重启或数据写入；
- 历史文档与实际代码可能不一致。

简单一次性只读问题可以不创建 Project Profile，但必须明确当前仓库和分支。

## 2. Onboarding 命令

```bash
python3 scripts/cp-runtime.py project-onboard \
  --repo-path /path/to/repo \
  --project-id logistics-system \
  --project-name "AI 物流管理系统"
```

指定自定义仓库外目录：

```bash
python3 scripts/cp-runtime.py project-onboard \
  --repo-path /path/to/repo \
  --context-dir /secure/external/context/logistics-system
```

## 3. 自动识别范围

工具只读取：

- Git 根目录、Branch、HEAD、Remote 和工作区状态；
- 根目录构建标记；
- 根目录一级模块标记；
- `pom.xml`、`package.json` 等有限文件中的框架或脚本声明。

不会：

- 深度扫描全部源码；
- 执行构建、测试或启动；
- 访问网络、数据库或生产环境；
- 读取 `.env` 并保存凭据；
- 将启发式推断标为已确认。

## 4. 校对 Profile

首次生成后重点检查：

1. `identity.repo_path` 和 `remote_origin`；
2. `technology` 是否遗漏主要技术栈；
3. `entrypoints` 的 `confidence`；
4. `boundaries` 中的环境、数据敏感等级、所有权；
5. `unknowns` 是否已经被实际证据解决；
6. `prohibited_paths` 是否覆盖依赖、构建产物和敏感目录。

## 5. 刷新与验证

```bash
python3 scripts/cp-runtime.py project-refresh \
  --profile /path/to/project-profile.json
```

```bash
python3 scripts/cp-runtime.py project-validate \
  --profile /path/to/project-profile.json \
  --repo-path /path/to/repo
```

刷新主要更新 Project State 的 Git 基线。Project Profile 的稳定绑定哈希只在项目身份或治理边界变化时改变。

## 6. 项目隔离

每个项目必须使用独立 Project ID 和目录。禁止：

- 复制 A 项目的 Profile 给 B 项目；
- 复用其他项目的 Approval；
- 把其他项目的接口、表结构、凭据和结论写入当前 Project Memory；
- 在同一个任务状态中切换仓库根目录；
- 依赖项目名称相同而忽略 Remote 和路径验证。
