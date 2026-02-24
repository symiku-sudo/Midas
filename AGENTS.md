# Project Skills
- sop: `dev_skills/sop/SKILL.md`
- feature: `dev_skills/feature/SKILL.md`
- bugfix: `dev_skills/bugfix/SKILL.md`
- refactor: `dev_skills/refactor/SKILL.md`
- review: `dev_skills/review/SKILL.md`
- doc: `dev_skills/doc/SKILL.md`
- issue: `dev_skills/issue/SKILL.md`
- run_main: `dev_skills/run_main/SKILL.md`
- cache-sync: `dev_skills/cache-sync/SKILL.md`

# Reference
- 工程参考指南：`dev_skills/engineering_guidelines.md`

# Trigger
- 默认优先触发 `sop`，再由 `sop` 路由到具体子 skill。
- 当请求已经明确任务类型（如“修 bug”“做 review”“改文档”）时，可直接触发对应子 skill。

# Midas Scope
- 当前仓库目标：个人多模态知识库助手（Midas）。
- 主要代码位置：`server/`（FastAPI 服务端）。
- 关键接口：`/health`、`/api/bilibili/summarize`、`/api/xiaohongshu/sync`。
- 交接文件：`WEEKLY_PROGRESS.md`。
