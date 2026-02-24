# Midas Server (MVP - Week 1)

## What is implemented

- `GET /health`
- `POST /api/bilibili/summarize`
- Unified response envelope: `ok/code/message/data/request_id`
- Unified error handling and request-id middleware
- Config-driven runtime (`config.yaml`)

## Quick start

```bash
cd server
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## API examples

```bash
curl http://127.0.0.1:8000/health
```

```bash
curl -X POST http://127.0.0.1:8000/api/bilibili/summarize \
  -H 'Content-Type: application/json' \
  -d '{"video_url":"https://www.bilibili.com/video/BV1xx411c7mD"}'
```

## Notes

- Default ASR mode is `mock` for local development.
- To use real ASR, install `faster-whisper` and set `asr.mode: faster_whisper`.
- To use real LLM output, set `llm.enabled: true` and configure API params.
