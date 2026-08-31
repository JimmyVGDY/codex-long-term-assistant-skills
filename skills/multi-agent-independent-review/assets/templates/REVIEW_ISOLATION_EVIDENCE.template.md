# Reviewer 运行时隔离证据

- 功能边界：
- 记录时间：
- 主协调 Agent：
- Reviewer Agent 类型：
- 实际 Agent 配置路径：
- Reviewer TOML 声明：
- 父会话实际沙箱：
- 子 Agent 运行时权限信息：
- 是否确认使用指定 Agent：
- 是否执行受控探针：
- 探针结果：未执行 / sandbox-denied / permission-denied / write-succeeded / invalid
- 探针环境：临时测试仓库 / 不适用
- 证据摘要：

## 隔离等级

- [ ] Level A：系统隔离复审（system-readonly）
- [ ] Level B：逻辑只读复审（logical-readonly）
- [ ] Level C：实施 Agent 自查（self-review）
- [ ] 未验证（unknown）

## 严格只读资格

- 是否满足：
- 判断依据：
- 限制与未验证项：

> 不得仅凭 `sandbox_mode = "read-only"` 声明判定系统隔离通过。受控写入探针只能在一次性临时仓库中执行，不能在正式项目或生产环境中自动执行。
