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

## `POST /api/xiaohongshu/sync`

Request:

```json
{
  "limit": 5
}
```

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

## Error codes

- `INVALID_INPUT`: request field invalid or config invalid
- `AUTH_EXPIRED`: upstream auth expired
- `RATE_LIMITED`: upstream throttling
- `CIRCUIT_OPEN`: sync stopped due to consecutive failures
- `UPSTREAM_ERROR`: third-party/downstream failure
- `DEPENDENCY_MISSING`: required local dependency missing
- `INTERNAL_ERROR`: unhandled server error
