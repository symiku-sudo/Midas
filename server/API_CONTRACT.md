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
  "min_score": 0.35
}
```

说明：
- `source` 可选：`bilibili` / `xiaohongshu`；为空时同时返回两类候选。
- `min_score` 范围 `0~1`。

Success `data`:

```json
{
  "total": 1,
  "items": [
    {
      "source": "bilibili",
      "note_ids": ["n1", "n2"],
      "score": 0.91,
      "reason_codes": ["KEYWORD_OVERLAP", "TITLE_SIMILAR"],
      "notes": [
        {"note_id": "n1", "title": "标题A", "saved_at": "2026-03-01 10:00:00"},
        {"note_id": "n2", "title": "标题B", "saved_at": "2026-03-01 11:00:00"}
      ]
    }
  ]
}
```

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
