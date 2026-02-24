---
name: issue
description: GitHub Issue 管理规范。用于 Midas 仓的新建、更新、去重和关闭流程。
---

# Issue（Issue 管理）

## 必须流程
1. 创建前先检索重复 issue（open + all）。
2. 命中同主题时优先编辑已有 issue，不重复新建。
3. 新建 issue 使用结构化模板：背景、复现、期望、风险、验收。
4. 新建后再次检索，确认无并发重复单。
5. 发现重复时保留 canonical issue，其他标记 duplicate 并关闭。

## 建议命令
```bash
gh issue list --state open --limit 200
gh issue list --state all --search "<keyword> in:title" --limit 20
```

## 交付要求
- canonical issue 编号与链接
- 检索关键词
- 被关闭重复 issue 列表（如有）
