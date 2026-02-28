---
name: doc
description: Midas 文档编写与维护规范。用于 README、API 契约等文档更新。
---

# Doc（文档维护）

## 必须流程
1. 明确文档目标读者与 DoD。
2. 先读相关文档，避免冲突和重复。
3. 仅做需求相关改动，保持结构一致。
4. 所有示例命令必须可执行或标注前置条件。
5. 自查术语一致：接口名、错误码、路径、配置项。

## Midas 文档优先级
1. `server/API_CONTRACT.md`
2. `server/README.md`
3. `README.md`
4. `dev_skills/doc/incidents/*.md`（事故复盘）

## 事故复盘文档规范
- 文件路径：`dev_skills/doc/incidents/YYYY-MM-DD-<topic>.md`
- 最小结构：
1. 背景与影响
2. 时间线（必须使用绝对日期时间）
3. 根因链路
4. 证据
5. 处置与回滚
6. 防再发动作（Owner + 截止日期）

## 交付要求
- 变更文件列表
- 关键改动摘要
- 验证说明（是否执行过示例命令）
