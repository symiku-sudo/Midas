---
name: sop
description: Midas 标准作业流程（SOP）。用于功能开发、缺陷修复、重构、评审、文档、issue 管理与运行调试，强调 DoD、计划、验证、交接与提交规范。
---

# SOP（标准作业流程）

## 路由规则
- 新增功能：`dev_skills/feature/SKILL.md`
- 缺陷修复：`dev_skills/bugfix/SKILL.md`
- 无行为改变重构：`dev_skills/refactor/SKILL.md`
- 代码评审：`dev_skills/review/SKILL.md`
- 文档维护：`dev_skills/doc/SKILL.md`
- Issue 管理：`dev_skills/issue/SKILL.md`
- 涉及排序/召回/候选推荐问题：必须进入 `dev_skills/bugfix/SKILL.md` 的“评分/召回/推荐类问题（强制流程）”。

## 标准流程（6 步）
1. 明确目标、范围和 DoD。
2. 给出实现计划（涉及文件、验证方式、风险）。
3. 小步改动并保持可回滚。
4. 运行验证（测试/启动/接口验证）。
5. 自查边界、安全、错误处理和文档一致性。
6. 输出变更摘要并提交。

## 有状态数据变更附加检查
- 当改动涉及数据库路径、缓存目录、进程启动目录（cwd）、配置重置或清理脚本时，必须额外完成：
1. 在改动前后打印并记录“实际生效路径”（例如 `xiaohongshu.db_path` 解析后的绝对路径）。
2. 验证重启后仍读取同一份数据文件（至少对比路径 + 记录条数）。
3. 若存在 `DELETE/clear/reset` 能力，默认增加显式确认（双确认文案或参数）。
4. 在交付说明中附“数据影响评估”：是否可能导致“看起来像被清空”。
5. 保护备份文件：默认不得删除/覆盖 `server/.tmp/backups/` 下的 `.db` 备份（含 `*_latest.db`），除非用户明确授权并记录影响评估。

## Midas 项目约束
- 统一响应协议不可破坏：`ok/code/message/data/request_id`。
- 关键错误码要可被客户端区分：`INVALID_INPUT`、`AUTH_EXPIRED`、`RATE_LIMITED`、`CIRCUIT_OPEN`、`UPSTREAM_ERROR`、`INTERNAL_ERROR`。
- 任何 API 变更必须同步更新：`server/API_CONTRACT.md`。
- 阶段收尾必须同步更新：`README.md` 与 `server/README.md`（按改动范围）。
- 备份保护是硬约束：清理/重置脚本必须默认保留 `server/.tmp/backups/`，若要删除必须显式二次确认并在交付说明中写明。
