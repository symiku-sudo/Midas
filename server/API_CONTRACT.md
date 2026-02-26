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

## Endpoints

## `GET /health`

- Purpose: connection test
- Success `data`:

```json
{
  "status": "ok"
}
```

## `POST /api/bilibili/summarize`

Request:

```json
{
  "video_url": "BV1xx411c7mD"
}
```

说明：
- `video_url` 支持完整链接（`https://www.bilibili.com/video/BV...`）或直接传 `BV` 号。

Success `data`:

```json
{
  "video_url": "...",
  "summary_markdown": "...",
  "elapsed_ms": 12345,
  "transcript_chars": 8888
}
```

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

## `POST /api/xiaohongshu/sync`

Request:

```json
{
  "limit": 5,
  "confirm_live": false
}
```

## `GET /api/xiaohongshu/sync/cooldown`

用途：查询“小红书真实同步”冷却状态（用于客户端倒计时与按钮禁用）。

Success `data`:

```json
{
  "mode": "web_readonly",
  "allowed": false,
  "remaining_seconds": 1260,
  "next_allowed_at_epoch": 1772100000,
  "last_sync_at_epoch": 1772098740,
  "min_interval_seconds": 1800
}
```

说明：
- `confirm_live` 仅在 `xiaohongshu.mode=web_readonly` 时需要设为 `true`。
- 默认 `false`，用于防止误触发真实账号请求。
- 对视频型笔记，会走“音频导出 -> ASR 转写 -> LLM 总结”，并合并正文（若存在）。
- `limit` 表示“有效同步目标条数”，对应 `new_count`。
- 命中去重表的笔记会计入 `skipped_count`，但不会占用 `limit` 名额。
- 服务端会自动翻页（cursor）继续拉取，直到：
  - `new_count >= limit`，或
  - 已遍历完当前收藏列表（即无更多可检查 `note_id`）。
- `fetched_count` 表示本次实际检查过的笔记条数（含跳过与失败）。

Success `data`:

```json
{
  "requested_limit": 5,
  "fetched_count": 5,
  "new_count": 5,
  "skipped_count": 0,
  "failed_count": 0,
  "circuit_opened": false,
  "summaries": [
    {
      "note_id": "mock-note-001",
      "title": "...",
      "source_url": "...",
      "summary_markdown": "..."
    }
  ]
}
```

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
- 因此同一 `note_id` 下次同步仍会被判定为重复并跳过。

## `POST /api/notes/xiaohongshu/synced/prune`

用途：清理去重表中“未保存到笔记库”的 `note_id`。

适用场景：
- 某次同步生成失败或未保存，导致后续被去重跳过。
- 希望让这部分条目在后续同步中可再次生成总结。

Success `data`:

```json
{
  "candidate_count": 7,
  "deleted_count": 7
}
```

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

## `POST /api/xiaohongshu/sync/jobs`

用途：创建异步同步任务（用于客户端显示实时进度）。

Request:

```json
{
  "limit": 5,
  "confirm_live": false
}
```

Success `data`:

```json
{
  "job_id": "6a9f....",
  "status": "pending",
  "requested_limit": 5
}
```

## `GET /api/xiaohongshu/sync/jobs/{job_id}`

用途：查询同步任务状态与进度。

Success `data`（运行中）:

```json
{
  "job_id": "6a9f....",
  "status": "running",
  "requested_limit": 5,
  "current": 2,
  "total": 5,
  "message": "已完成有效同步：2/5（mock-note-002）",
  "result": null,
  "error": null
}
```

Success `data`（完成）:

```json
{
  "job_id": "6a9f....",
  "status": "succeeded",
  "requested_limit": 5,
  "current": 5,
  "total": 5,
  "message": "同步任务完成。",
  "result": {
    "requested_limit": 5,
    "fetched_count": 5,
    "new_count": 5,
    "skipped_count": 0,
    "failed_count": 0,
    "circuit_opened": false,
    "summaries": []
  },
  "error": null
}
```

## Error codes

- `INVALID_INPUT`: request field invalid or config invalid
- `AUTH_EXPIRED`: upstream auth expired
- `RATE_LIMITED`: upstream throttling
- `CIRCUIT_OPEN`: sync stopped due to consecutive failures
- `UPSTREAM_ERROR`: third-party/downstream failure
- `DEPENDENCY_MISSING`: required local dependency missing
- `INTERNAL_ERROR`: unhandled server error
