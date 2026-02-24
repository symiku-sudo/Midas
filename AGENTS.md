# AGENTS.md instructions for /mnt/d/MyWork/midas

## Skills
A skill is a local instruction set stored in a `SKILL.md` file.
Use the following list as the imported skill registry for this repository.

### Available skills
- `sop`: Midas 标准作业流程（SOP），用于路由功能开发/修复/重构/评审/文档/运行流程。 (file: `/mnt/d/MyWork/midas/dev_skills/sop/SKILL.md`)
- `feature`: 在 Midas 中实现新功能或增强能力。 (file: `/mnt/d/MyWork/midas/dev_skills/feature/SKILL.md`)
- `bugfix`: 诊断并修复 Midas 缺陷或回归。 (file: `/mnt/d/MyWork/midas/dev_skills/bugfix/SKILL.md`)
- `refactor`: 在不改变外部行为的前提下优化代码结构。 (file: `/mnt/d/MyWork/midas/dev_skills/refactor/SKILL.md`)
- `review`: 对改动做结构化评审，关注正确性、风险和测试缺口。 (file: `/mnt/d/MyWork/midas/dev_skills/review/SKILL.md`)
- `doc`: 维护 README/API 契约/计划/交接等文档。 (file: `/mnt/d/MyWork/midas/dev_skills/doc/SKILL.md`)
- `issue`: GitHub Issue 新建、更新、去重与关闭流程。 (file: `/mnt/d/MyWork/midas/dev_skills/issue/SKILL.md`)
- `run_main`: 本地闭环运行（测试/启动/接口验证 -> 修复 -> 重跑）。 (file: `/mnt/d/MyWork/midas/dev_skills/run_main/SKILL.md`)
- `cache-sync`: 开发缓存清理与环境一致性恢复。 (file: `/mnt/d/MyWork/midas/dev_skills/cache-sync/SKILL.md`)

### Reference
- 工程参考指南：`/mnt/d/MyWork/midas/dev_skills/engineering_guidelines.md`

### Trigger rules
- 默认优先使用 `sop`，再由 `sop` 路由到具体子 skill。
- 当请求明确指定任务类型（如“修 bug”“做 review”“改文档”）时，可直接使用对应子 skill。
- 若请求显式点名 skill（如 `$bugfix`），优先按点名 skill 执行。

## Midas Scope
- 项目目标：个人多模态知识库助手（Midas）。
- 当前主开发目录：`server/`（FastAPI 服务端）。
- 关键接口：`/health`、`/api/bilibili/summarize`、`/api/xiaohongshu/sync`。
- 交接文档：`WEEKLY_PROGRESS.md`。
