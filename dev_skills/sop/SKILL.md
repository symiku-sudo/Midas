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
- 运行闭环：`dev_skills/run_main/SKILL.md`
- 缓存同步：`dev_skills/cache-sync/SKILL.md`

## 标准流程（6 步）
1. 明确目标、范围和 DoD。
2. 给出实现计划（涉及文件、验证方式、风险）。
3. 小步改动并保持可回滚。
4. 运行验证（测试/启动/接口验证）。
5. 自查边界、安全、错误处理和文档一致性。
6. 输出变更摘要并提交。

## Midas 项目约束
- 统一响应协议不可破坏：`ok/code/message/data/request_id`。
- 关键错误码要可被客户端区分：`INVALID_INPUT`、`AUTH_EXPIRED`、`RATE_LIMITED`、`CIRCUIT_OPEN`、`UPSTREAM_ERROR`、`INTERNAL_ERROR`。
- 任何 API 变更必须同步更新：`server/API_CONTRACT.md`。
- 阶段收尾必须更新：`WEEKLY_PROGRESS.md`。
