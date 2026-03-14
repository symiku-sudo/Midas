# Midas Server API Contract (MVP)

## Unified envelope

Success:

```json
{
  "ok": true,
  "code": "OK",
  "message": "",
  "data": {},
  "request_id": "uuid"
}
```

Failure:

```json
{
  "ok": false,
  "code": "INVALID_INPUT",
  "message": "...",
  "data": null,
  "request_id": "uuid"
}
```

## Authentication

- 默认关闭。
- 当 `config.yaml` 配置了 `auth.access_token` 且非空时，除 `GET /health` 外的接口都需要携带 `Authorization: Bearer <token>` 或 `X-Midas-Token: <token>`。
- 缺失或错误时返回 `401` + `AUTH_EXPIRED`。

## Endpoints

## `GET /health`

- Purpose: connection test
- Success `data`:

```json
{
  "status": "ok"
}
```

## `GET /api/finance/signals`

用途：读取 Finance Signals 面板所需状态（由 `server/finance_signals/main.py` 持续写入本地 JSON）。

Success `data`:

```json
{
  "update_time": "2026-03-05 12:00:00",
  "news_last_fetch_time": "2026-03-05 11:58:00",
  "news_stale": false,
  "watchlist_preview": [
    {
      "name": "布伦特原油",
      "symbol": "BZ=F",
      "price": 91.23,
      "change_pct": "+1.2%",
      "alert_hint": ">90",
      "alert_active": true,
      "related_news_count": 1,
      "related_keywords": ["原油"]
    }
  ],
  "top_news": [
    {
      "title": "美联储官员释放降息信号",
      "link": "https://example.com/news-1",
      "publisher": "Reuters",
      "published": "2026-03-05 11:40:00",
      "category": "finance",
      "matched_keywords": ["美联储", "降息"],
      "related_symbols": ["BZ=F"],
      "related_watchlist_names": ["布伦特原油"]
    }
  ],
  "focus_cards": [
    {
      "title": "布伦特原油 已触发监控阈值",
      "summary": "阈值条件：>90；最近关联新闻 1 条",
      "priority": "HIGH",
      "kind": "ALERT",
      "action_type": "REVIEW_NOW",
      "action_label": "立即复核",
      "action_hint": "先看价格异动和关联新闻，再决定是否提升观察频率。",
      "reasons": ["threshold_triggered", "related_news_present"],
      "related_symbols": ["BZ=F"],
      "related_watchlist_names": ["布伦特原油"]
    }
  ],
  "watchlist_ntfy_enabled": true,
  "ai_insight_text": "## 24小时摘要\n\n- 原油与黄金波动加剧，市场重新计价通胀与降息路径。\n\n## 核心主线\n\n- 能源价格与利率预期成为共振主线。",
  "news_debug": {
    "entries_scanned": 40,
    "entries_filtered_by_source": 3,
    "matched_entries_count": 14,
    "top_news_count": 5,
    "digest_item_count": 12,
    "digest_prompt_chars": 5241,
    "digest_status": "generated",
    "digest_last_generated_at": "2026-03-05 12:00:00",
    "top_unmatched_titles": [
      "地方政策解读长文"
    ]
  },
  "market_alert_debug": {
    "alert_enabled": true,
    "alert_sent": true,
    "last_alert_time": "2026-03-05 12:00:00",
    "last_alert_signature": "布伦特原油（BZ=F）触发：价格突破 90",
    "last_alert_summary": "布伦特原油（BZ=F）触发：价格突破 90",
    "last_alert_status": "sent"
  }
}
```

说明：
- 若状态文件尚未生成，接口会返回空列表和初始化提示文案，HTTP 仍为 `200`。
- 若状态文件内容损坏，接口返回 `UPSTREAM_ERROR`。
- `news_last_fetch_time` / `news_stale` 用于客户端识别新闻抓取是否陈旧。
- `top_news` 为“今日金融与时政新闻 Top5”结构化列表，已按时效、来源权重、主题关键词和跨源覆盖加权后去重。
- `focus_cards` 为服务端按规则生成的“今日关注建议”，当前会优先覆盖“阈值已触发的标的”和“明确影响 watchlist 的新闻”两类信号。
- `focus_cards[].action_type` 为结构化动作类型，当前包括 `REVIEW_NOW`、`FOLLOW_UP`、`MONITOR`。
- `focus_cards[].action_label/action_hint` 提供建议动作和一句解释，便于客户端直接展示“现在该做什么”。
- `focus_cards[].reasons` 为触发理由代码，当前会覆盖 `threshold_triggered`、`related_news_present`、`keyword_overlap`、`recent_alert_sent`、`news_impacts_watchlist`、`linked_alert_active`、`multi_asset_impact`。
- `watchlist_preview[].related_news_count/related_keywords` 表示该关注标的在当前 Top5 新闻里的关联数量与命中关键词。
- `top_news[].related_symbols/related_watchlist_names` 表示该新闻可能影响的关注标的，服务端会根据 `finance_signals/financial_config.yaml` 里的 `market_data.instruments[].aliases` 做映射。
- `watchlist_ntfy_enabled` 表示 Watchlist 行情阈值 ntfy 通知当前开关状态。
- `ai_insight_text` 仅在用户主动触发摘要按钮后写入；未触发时允许为空字符串。
- `news_debug` 用于排查“有新闻但未进入 Top5”的召回/排序问题，以及观察 24 小时摘要的样本数与单次 prompt 文本长度。
- `news_debug.entries_filtered_by_source` 反映白名单/黑名单过滤效果。
- `news_debug.digest_item_count/digest_prompt_chars/digest_status/digest_last_generated_at` 分别表示摘要样本数、单次 prompt 字符数、摘要生成状态和最近一次真实生成时间。
- `market_alert_debug` 反映 Watchlist 行情阈值通知的发送状态。

## `PUT /api/finance/signals/watchlist-ntfy`

用途：切换 Watchlist 行情阈值的 ntfy 通知开关。

Request:

```json
{
  "enabled": false
}
```

## `POST /api/finance/signals/digest`

用途：按按钮触发“24 小时新闻摘要”生成，并把结果写回 Finance Signals 状态文件。

行为说明：
- 若距离上一次真实生成不足 `3` 小时（由 `news.digest.reuse_within_seconds` 控制），直接复用上次摘要结果，不再调用 LLM。
- 若超过 `3` 小时，则基于最近 `24` 小时新闻样本重新生成。
- 返回值结构与 `GET /api/finance/signals` 相同，便于客户端直接刷新当前面板状态。

Success `data`:

```json
{
  "update_time": "2026-03-10 18:00:00",
  "news_last_fetch_time": "2026-03-10 18:00:00",
  "news_stale": false,
  "watchlist_preview": [],
  "top_news": [],
  "watchlist_ntfy_enabled": false,
  "ai_insight_text": "## 24小时摘要\n\n- 已生成。",
  "news_debug": {
    "digest_item_count": 12,
    "digest_prompt_chars": 1412,
    "digest_status": "generated",
    "digest_last_generated_at": "2026-03-10 18:00:00"
  },
  "market_alert_debug": {
    "alert_enabled": false,
    "alert_sent": false,
    "last_alert_time": "",
    "last_alert_signature": "",
    "last_alert_summary": "",
    "last_alert_status": ""
  }
}
```

## `POST /api/assets/fill-from-images`

用途：接收资产截图（最多 5 张），由服务端调用多模态 LLM 提取金额并按资产分类汇总，供客户端回填输入框。

Request：
- `Content-Type: multipart/form-data`
- 表单字段：`images`（可重复，上传 1~5 张图片）

Success `data`:

```json
{
  "image_count": 3,
  "category_amounts": {
    "stock": 12.34,
    "equity_fund": 5.20,
    "gold": 1.00,
    "bond_and_bond_fund": 0.00,
    "money_market_fund": 2.10,
    "bank_fixed_deposit": 20.00,
    "bank_current_deposit": 3.50,
    "housing_fund": 8.88
  },
  "total_amount_wan": 53.02
}
```

说明：
- 金额单位统一为“万元人民币”。
- `category_amounts` 始终返回完整分类键集合，缺失项返回 `0.00`。
- 服务端仅返回识别结果，不会触发保存动作；客户端需由用户手动确认并保存。

## `GET /api/assets/current`

用途：读取服务端持久化的“当前资产金额”。客户端卸载重装或切换设备后，会先以该接口恢复当前填写值。

Success `data`:

```json
{
  "total_amount_wan": 15.5,
  "amounts": {
    "stock": 12.0,
    "gold": 3.5
  }
}
```

说明：
- 资产分类金额单位统一为“万元人民币”。
- 首次尚未保存时，接口返回 `total_amount_wan=0` 和空 `amounts`。

## `PUT /api/assets/current`

用途：保存当前资产金额。该接口只更新“当前值”，不会追加历史快照；若客户端希望保留时间序列历史，应额外调用 `POST /api/assets/snapshots`。

Request:

```json
{
  "total_amount_wan": 15.5,
  "amounts": {
    "stock": 12.0,
    "gold": 3.5
  }
}
```

Success `data`:

```json
{
  "total_amount_wan": 15.5,
  "amounts": {
    "stock": 12.0,
    "gold": 3.5
  }
}
```

说明：
- 若 `total_amount_wan <= 0` 且 `amounts` 非空，服务端会自动按分类求和。
- 仅允许已定义的资产分类键。

## `GET /api/assets/snapshots`

用途：读取服务端持久化的资产快照历史。卸载重装/换设备后，客户端可据此恢复历史记录。

Success `data`:

```json
{
  "total": 2,
  "items": [
    {
      "id": "asset-history-2",
      "saved_at": "2026-03-08 14:40:00",
      "total_amount_wan": 15.5,
      "amounts": {
        "stock": 12.0,
        "gold": 3.5
      }
    },
    {
      "id": "asset-history-1",
      "saved_at": "2026-03-07 21:10:00",
      "total_amount_wan": 14.2,
      "amounts": {
        "stock": 11.0,
        "gold": 3.2
      }
    }
  ]
}
```

说明：
- 排序规则：`saved_at` 近到远。
- 资产分类金额单位统一为“万元人民币”。

## `POST /api/assets/snapshots`

用途：保存或迁移一条资产快照历史记录。`id` 已存在时会执行幂等更新，便于客户端把本地旧历史补传到服务端。

Request:

```json
{
  "id": "asset-history-2",
  "saved_at": "2026-03-08 14:40:00",
  "total_amount_wan": 15.5,
  "amounts": {
    "stock": 12.0,
    "gold": 3.5
  }
}
```

Success `data`:

```json
{
  "id": "asset-history-2",
  "saved_at": "2026-03-08 14:40:00",
  "total_amount_wan": 15.5,
  "amounts": {
    "stock": 12.0,
    "gold": 3.5
  }
}
```

说明：
- `id` / `saved_at` 允许客户端显式传入，便于迁移本地旧记录。
- 若 `id` 为空，服务端会自动生成。
- 若 `total_amount_wan <= 0` 且 `amounts` 非空，服务端会自动按分类求和。

## `DELETE /api/assets/snapshots/{record_id}`

用途：删除一条服务端资产快照历史。

Success `data`:

```json
{
  "deleted_count": 1
}
```

## `POST /api/jobs/bilibili-summarize`

用途：以异步任务方式提交 B 站总结，请求会立即返回 `job_id`，实际总结由服务端后台 worker 顺序执行。

Request:

```json
{
  "video_url": "BV1xx411c7mD"
}
```

Success `data`:

```json
{
  "job_id": "9a7c4a1b4f6d4f1dbde7bdfce95d0d0e",
  "job_type": "bilibili_summarize",
  "status": "PENDING",
  "message": "任务已入队，等待执行。",
  "submitted_at": "2026-03-12 12:30:00",
  "retry_of_job_id": ""
}
```

说明：
- `video_url` 规则与同步接口 `POST /api/bilibili/summarize` 一致。
- 历史任务会持久化到 `server/.tmp/async_jobs.json`。

## `POST /api/jobs/xiaohongshu/summarize-url`

用途：以异步任务方式提交小红书单篇 URL 总结，请求会立即返回 `job_id`。

Request:

```json
{
  "url": "https://www.xiaohongshu.com/explore/67b8d0d1000000001d03f09a"
}
```

Success `data`:

```json
{
  "job_id": "92efc62e49024659adf843d60e2f7b16",
  "job_type": "xiaohongshu_summarize_url",
  "status": "PENDING",
  "message": "任务已入队，等待执行。",
  "submitted_at": "2026-03-12 12:31:00",
  "retry_of_job_id": ""
}
```

## `GET /api/jobs`

用途：读取最近异步任务历史。

Query：
- `limit`：返回条数，默认 `20`，范围 `1~100`
- `status`：可选，按 `PENDING/RUNNING/SUCCEEDED/FAILED/INTERRUPTED` 过滤
- `job_type`：可选，当前支持 `bilibili_summarize`、`xiaohongshu_summarize_url`

Success `data`:

```json
{
  "total": 1,
  "items": [
    {
      "job_id": "9a7c4a1b4f6d4f1dbde7bdfce95d0d0e",
      "job_type": "bilibili_summarize",
      "status": "SUCCEEDED",
      "message": "任务执行完成。",
      "submitted_at": "2026-03-12 12:30:00",
      "started_at": "2026-03-12 12:30:01",
      "finished_at": "2026-03-12 12:31:00",
      "retry_of_job_id": ""
    }
  ]
}
```

字段说明：
- `retry_of_job_id`：若本任务由历史失败/中断任务重试创建，则这里会记录原任务 `job_id`；首次提交时为空字符串。

## `GET /api/jobs/{job_id}`

用途：读取单个异步任务状态和结果。

Success `data`:

```json
{
  "job_id": "9a7c4a1b4f6d4f1dbde7bdfce95d0d0e",
  "job_type": "bilibili_summarize",
  "status": "SUCCEEDED",
  "message": "任务执行完成。",
  "submitted_at": "2026-03-12 12:30:00",
  "started_at": "2026-03-12 12:30:01",
  "finished_at": "2026-03-12 12:31:00",
  "retry_of_job_id": "",
  "request_payload": {
    "video_url": "https://www.bilibili.com/video/BV1xx411c7mD"
  },
  "result": {
    "video_url": "https://www.bilibili.com/video/BV1xx411c7mD",
    "summary_markdown": "# 总结",
    "elapsed_ms": 1234,
    "transcript_chars": 4567
  },
  "error": null
}
```

失败说明：
- 当 `job_id` 不存在时，返回 `404` + `JOB_NOT_FOUND`。
- 服务启动时若发现历史任务残留在 `RUNNING`，会将其改写为 `INTERRUPTED`，并保留原请求体以便重新提交。

## `POST /api/jobs/{job_id}/retry`

用途：重试单个异步任务。当前仅支持 `FAILED` 或 `INTERRUPTED` 状态。

Success `data`:

```json
{
  "job_id": "4fd0a8dcb6d0493f8df59cbb0c383d91",
  "job_type": "bilibili_summarize",
  "status": "PENDING",
  "message": "任务已入队，等待执行。",
  "submitted_at": "2026-03-12 12:40:00",
  "retry_of_job_id": "9a7c4a1b4f6d4f1dbde7bdfce95d0d0e"
}
```

失败说明：
- 当 `job_id` 不存在时，返回 `404` + `JOB_NOT_FOUND`。
- 当原任务不是 `FAILED/INTERRUPTED`，或缺少原始请求参数时，返回 `400` + `INVALID_INPUT`。

## `POST /api/bilibili/summarize`

Request:

```json
{
  "video_url": "BV1xx411c7mD"
}
```

说明：
- `video_url` 支持完整链接（`https://www.bilibili.com/video/BV...`）或直接传 `BV` 号。
- 新生成的 `summary_markdown` 会追加“`## 评论区洞察（含点赞权重）`”章节（best-effort，不影响主摘要返回）。

Success `data`:

```json
{
  "video_url": "...",
  "summary_markdown": "...",
  "elapsed_ms": 12345,
  "transcript_chars": 8888
}
```

说明：
- 保存成功后会自动备份一次笔记数据库到 `server/.tmp/backups/`。

## `POST /api/notes/bilibili/save`

用途：手动保存一次 B 站总结结果到笔记库。

Request:

```json
{
  "video_url": "https://www.bilibili.com/video/BV...",
  "summary_markdown": "# 总结...",
  "elapsed_ms": 12345,
  "transcript_chars": 8888,
  "title": "可选标题"
}
```

Success `data`:

```json
{
  "note_id": "9b7f....",
  "title": "可选标题",
  "video_url": "https://www.bilibili.com/video/BV...",
  "summary_markdown": "# 总结...",
  "elapsed_ms": 12345,
  "transcript_chars": 8888,
  "saved_at": "2026-02-25 13:20:00"
}
```

说明：
- 保存成功后会自动备份一次笔记数据库到 `server/.tmp/backups/`。

## `GET /api/notes/bilibili`

用途：按时间倒序列出已保存 B 站笔记。

Success `data`:

```json
{
  "total": 2,
  "items": [
    {
      "note_id": "9b7f....",
      "title": "可选标题",
      "video_url": "https://www.bilibili.com/video/BV...",
      "summary_markdown": "# 总结...",
      "elapsed_ms": 12345,
      "transcript_chars": 8888,
      "saved_at": "2026-02-25 13:20:00"
    }
  ]
}
```

## `GET /api/notes/search`

用途：统一检索已保存笔记，当前会聚合 B 站和小红书结果，支持关键词、来源、分页。

Query：
- `keyword`：可选，按标题和摘要内容模糊匹配
- `source`：可选，支持 `bilibili`、`xiaohongshu`
- `limit`：默认 `50`，范围 `1~200`
- `offset`：默认 `0`

Success `data`:

```json
{
  "total": 2,
  "limit": 20,
  "offset": 0,
  "items": [
    {
      "source": "xiaohongshu",
      "note_id": "x1",
      "title": "美联储观察",
      "source_url": "https://www.xiaohongshu.com/explore/x1",
      "summary_markdown": "# 降息交易",
      "saved_at": "2026-03-03 08:00:00"
    },
    {
      "source": "bilibili",
      "note_id": "b1",
      "title": "宏观复盘",
      "source_url": "https://www.bilibili.com/video/BV1xx411c7mD",
      "summary_markdown": "# 美联储与降息",
      "saved_at": "2026-03-01 08:00:00"
    }
  ]
}
```

## `DELETE /api/notes/bilibili/{note_id}`

用途：删除单条已保存 B 站笔记。

Success `data`:

```json
{
  "deleted_count": 1
}
```

## `DELETE /api/notes/bilibili`

用途：清空所有已保存 B 站笔记。

Success `data`:

```json
{
  "deleted_count": 12
}
```

## `POST /api/xiaohongshu/summarize-url`

用途：按指定小红书笔记 URL 总结单篇内容（支持图文与视频笔记）。

Request:

```json
{
  "url": "https://www.xiaohongshu.com/explore/xxxxxx"
}
```

Success `data`:

```json
{
  "note_id": "xxxxxx",
  "title": "笔记标题",
  "source_url": "https://www.xiaohongshu.com/explore/xxxxxx",
  "summary_markdown": "# 总结..."
}
```

说明：
- 对视频型笔记，会走“音频导出 -> ASR 转写 -> LLM 总结”，并合并正文（若存在）。
- 总结成功后会自动写入去重表 `xiaohongshu_synced_notes`。
- 新生成的 `summary_markdown` 会追加“`## 评论区洞察（含点赞权重）`”章节（best-effort，不影响主摘要返回）。

## `POST /api/notes/xiaohongshu/save-batch`

用途：批量保存小红书总结结果到笔记库。

Request:

```json
{
  "notes": [
    {
      "note_id": "mock-note-001",
      "title": "...",
      "source_url": "...",
      "summary_markdown": "..."
    }
  ]
}
```

Success `data`:

```json
{
  "saved_count": 1
}
```

## `GET /api/notes/xiaohongshu`

用途：按时间倒序列出已保存小红书笔记。

Success `data`:

```json
{
  "total": 2,
  "items": [
    {
      "note_id": "mock-note-001",
      "title": "...",
      "source_url": "...",
      "summary_markdown": "...",
      "saved_at": "2026-02-25 13:20:00"
    }
  ]
}
```

## `DELETE /api/notes/xiaohongshu/{note_id}`

用途：删除单条已保存小红书笔记。

Success `data`:

```json
{
  "deleted_count": 1
}
```

## `DELETE /api/notes/xiaohongshu`

用途：清空所有已保存小红书笔记。

Success `data`:

```json
{
  "deleted_count": 8
}
```

说明：
- 删除“已保存笔记”不会删除去重表 `xiaohongshu_synced_notes` 里的 `note_id`。
- 因此同一 `note_id` 后续按 URL 总结仍会被判定为已处理。

## `POST /api/notes/xiaohongshu/synced/prune`

用途：清理去重表中“未保存到笔记库”的 `note_id`。

适用场景：
- 某次按 URL 总结生成后未保存，导致后续被去重跳过。
- 希望让这部分条目在后续按 URL 总结时可再次生成总结。

Success `data`:

```json
{
  "candidate_count": 7,
  "deleted_count": 7
}
```

## `POST /api/notes/merge/suggest`

用途：发现可合并候选（当前仅同源：B 站 / 小红书）。

Request:

```json
{
  "source": "bilibili",
  "limit": 20,
  "min_score": 0.35,
  "include_weak": false
}
```

说明：
- `source` 可选：`bilibili` / `xiaohongshu`；为空时同时返回两类候选。
- `min_score` 范围 `0~1`。
- `include_weak` 默认 `false`，仅返回强相关候选；设为 `true` 时会额外返回中相关（`WEAK`）候选。

Success `data`:

```json
{
  "total": 1,
  "items": [
    {
      "source": "bilibili",
      "note_ids": ["n1", "n2"],
      "score": 0.91,
      "relation_level": "STRONG",
      "reason_codes": ["KEYWORD_OVERLAP", "SUMMARY_SIMILAR", "RELATION_STRONG"],
      "notes": [
        {"note_id": "n1", "title": "标题A", "saved_at": "2026-03-01 10:00:00"},
        {"note_id": "n2", "title": "标题B", "saved_at": "2026-03-01 11:00:00"}
      ]
    }
  ]
}
```

说明：
- 候选评分仅基于 `summary_similarity + keyword_overlap`。
- `relation_level`：`STRONG`（强相关）/ `WEAK`（中相关）。
- 默认仅返回 `STRONG` 候选；传 `include_weak=true` 时会返回 `WEAK`。

## `POST /api/notes/merge/preview`

用途：生成候选对的合并预览稿（不落库）。

Request:

```json
{
  "source": "bilibili",
  "note_ids": ["n1", "n2"]
}
```

Success `data`:

```json
{
  "source": "bilibili",
  "note_ids": ["n1", "n2"],
  "merged_title": "合并后标题",
  "merged_summary_markdown": "# 合并正文...",
  "source_refs": ["https://...", "https://..."],
  "conflict_markers": ["TITLE_CONFLICT"]
}
```

## `POST /api/notes/merge/commit`

用途：提交合并结果，默认非破坏（保留原笔记，新增 merged 笔记）。

Request:

```json
{
  "source": "bilibili",
  "note_ids": ["n1", "n2"],
  "merged_title": "可选覆盖标题",
  "merged_summary_markdown": "可选覆盖正文"
}
```

Success `data`:

```json
{
  "merge_id": "merge_xxx",
  "status": "MERGED_PENDING_CONFIRM",
  "source": "bilibili",
  "merged_note_id": "merged_note_xxx",
  "source_note_ids": ["n1", "n2"],
  "can_rollback": true,
  "can_finalize": true
}
```

说明：
- 此状态下可执行“回退”或“确认合并结果（破坏性）”。
- 创建 merged 笔记时，`merged_summary_markdown` 末尾会追加 `## 原始笔记来源`，
  按“原始标题 + 可点击链接”列出来源笔记。

## `POST /api/notes/merge/rollback`

用途：回退最近一次未 finalize 的合并（恢复到合并前状态）。

Request:

```json
{
  "merge_id": "merge_xxx"
}
```

Success `data`:

```json
{
  "merge_id": "merge_xxx",
  "status": "ROLLED_BACK",
  "deleted_merged_count": 1,
  "restored_source_count": 2
}
```

## `POST /api/notes/merge/finalize`

用途：确认合并结果并执行破坏性收尾（删除原笔记，仅保留 merged）。

Request:

```json
{
  "merge_id": "merge_xxx",
  "confirm_destructive": true
}
```

Success `data`:

```json
{
  "merge_id": "merge_xxx",
  "status": "FINALIZED_DESTRUCTIVE",
  "deleted_source_count": 2,
  "kept_merged_note_id": "merged_note_xxx"
}
```

说明：
- `confirm_destructive` 必须为 `true`，否则返回 `400 INVALID_INPUT`。
- 一旦 `FINALIZED_DESTRUCTIVE`，该 `merge_id` 不再允许 `rollback`。

## `POST /api/xiaohongshu/capture/refresh`

用途：自动更新小红书 auth 抓包配置并刷新运行时请求头。

行为：
- 先读取 `config.yaml` 的 `xiaohongshu.web_readonly.har_capture_path`。
- 若 HAR 不可用或不合法，则回退读取 `xiaohongshu.web_readonly.curl_capture_path`。
- 若两者都不可用，返回 `400 INVALID_INPUT`。

Success `data`:

```json
{
  "har_path": "/mnt/d/MyWork/midas/server/.tmp/xhs_detail.har",
  "request_url_host": "edith.xiaohongshu.com",
  "request_method": "GET",
  "headers_count": 18,
  "non_empty_keys": 8,
  "empty_keys": ["XHS_HEADER_COOKIE"]
}
```

说明：
- 字段名 `har_path` 为兼容保留；当回退到 cURL 时，该字段会返回 cURL 文件路径。

失败场景：
- HAR/cURL 不包含 `Cookie`：返回 `400 INVALID_INPUT`，提示重新导出包含敏感数据的抓包。

## `POST /api/xiaohongshu/auth/update`

用途：由客户端（如 Android WebView 登录页）直接上传 Cookie/UA，更新小红书鉴权配置。

Request:

```json
{
  "cookie": "a=1; b=2",
  "user_agent": "Mozilla/5.0 (Linux; Android 14)",
  "origin": "https://www.xiaohongshu.com",
  "referer": "https://www.xiaohongshu.com/"
}
```

Success `data`:

```json
{
  "updated_keys": [
    "XHS_HEADER_COOKIE",
    "XHS_HEADER_ORIGIN",
    "XHS_HEADER_REFERER",
    "XHS_HEADER_USER_AGENT"
  ],
  "non_empty_keys": 4,
  "cookie_pairs": 2
}
```

说明：
- 会写入 `server/.env` 并立即刷新运行时配置（无需手动重启）。
- `cookie` 必填，其他字段可选；未提供时保留原值。

## `GET /api/config/editable`

用途：读取“可由客户端修改”的配置子集（已排除敏感项）。

Success `data`:

```json
{
  "settings": {
    "llm": {
      "enabled": true,
      "api_base": "https://...",
      "model": "gemini-3-flash-preview",
      "timeout_seconds": 120
    },
    "xiaohongshu": {
      "default_limit": 20,
      "max_limit": 30
    }
  }
}
```

## `PUT /api/config/editable`

用途：更新可编辑配置（部分字段更新）。

Request:

```json
{
  "settings": {
    "xiaohongshu": {
      "default_limit": 8
    },
    "runtime": {
      "log_level": "DEBUG"
    }
  }
}
```

Success `data`:

```json
{
  "settings": {
    "xiaohongshu": {
      "default_limit": 8
    },
    "runtime": {
      "log_level": "DEBUG"
    }
  }
}
```

说明：
- 敏感字段不可更新（如 `llm.api_key`、`xiaohongshu.cookie`、`web_readonly.request_headers`）。
- 更新成功后，服务会热加载新配置用于后续请求。

## `POST /api/config/editable/reset`

用途：将可编辑配置恢复到默认值（基于 `config.example.yaml`）。

Success `data`:

```json
{
  "settings": {
    "runtime": {
      "log_level": "INFO"
    },
    "xiaohongshu": {
      "default_limit": 20
    }
  }
}
```

## Error codes

- `INVALID_INPUT`: request field invalid or config invalid
- `AUTH_EXPIRED`: upstream auth expired
- `RATE_LIMITED`: upstream throttling
- `CIRCUIT_OPEN`: request blocked by circuit-breaker
- `MERGE_NOT_FOUND`: merge history not found
- `MERGE_NOT_ALLOWED`: merge state/action is not allowed
- `UPSTREAM_ERROR`: third-party/downstream failure
- `DEPENDENCY_MISSING`: required local dependency missing
- `INTERNAL_ERROR`: unhandled server error
