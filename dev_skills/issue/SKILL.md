---
name: issue
description: GitHub Issue 管理流程。用于 Midas 仓库中 issue 的新建、更新、去重、关闭和状态同步。
---

# Issue（Issue 管理）

## 1) 必须流程
1. 创建前先检索重复 issue（open + all）。
2. 命中同主题时优先更新已有 issue，避免重复创建。
3. 新建 issue 使用结构化模板：背景、复现、期望、风险、验收。
4. 新建后再次检索，确认无并发重复单。
5. 发现重复时保留 canonical issue，其余标记 duplicate 并关闭。

## 2) 结束门禁（任一不满足都不能结束）
- 未提供检索关键词与结果证据，不能结束。
- 存在重复 issue 但未给出 canonical 选择理由，不能结束。
- 关闭重复单但未留下互链关系，不能结束。

## 3) 建议命令
```bash
gh issue list --state open --limit 200
gh issue list --state all --search "<keyword> in:title" --limit 20
```

## 4) 统一交付模板
- canonical issue 编号与链接。
- 检索关键词与检索范围。
- 新建/更新要点摘要。
- 被关闭重复 issue 列表（如有）。
