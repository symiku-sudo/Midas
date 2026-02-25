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
  "video_url": "https://www.bilibili.com/video/BV..."
}
```

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

说明：
- `confirm_live` 仅在 `xiaohongshu.mode=web_readonly` 时需要设为 `true`。
- 默认 `false`，用于防止误触发真实账号请求。

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
  "message": "已处理笔记：mock-note-002",
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
