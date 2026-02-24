# Midas Server (MVP - Week 2)

## What is implemented

- `GET /health`
- `POST /api/bilibili/summarize`
- `POST /api/xiaohongshu/sync`
- `POST /api/xiaohongshu/sync/jobs`
- `GET /api/xiaohongshu/sync/jobs/{job_id}`
- Unified response envelope: `ok/code/message/data/request_id`
- Unified error handling and request-id middleware
- Config-driven runtime (`config.yaml`)
- Xiaohongshu sync controls: limit, dedupe(SQLite), circuit-breaker
- API schema reference: `API_CONTRACT.md`

## Quick start

```bash
cd server
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Real-run config (Bilibili path)

```bash
cd server
cp config.real.example.yaml config.yaml
```

Then fill:
- `llm.api_key`
- Ensure `yt-dlp` and `ffmpeg` are installed on system
- Install `faster-whisper` if `asr.mode=faster_whisper`

## Safe live mode (Xiaohongshu, read-only)

服务端支持 `xiaohongshu.mode=web_readonly` 的低风险只读模式：
- 只允许 `GET/POST` 单请求回放
- 强制 HTTPS + 域名白名单
- 需要显式 `confirm_live=true`
- 带最小同步间隔保护（默认 1800 秒）

建议流程：
1. 在浏览器 DevTools 里抓“小红书收藏列表”请求。
2. 用脚本自动转换抓包到本地配置（避免手填出错）：
   ```bash
   cd server
   python tools/xhs_capture_to_config.py --har /path/to/capture.har
   ```
3. 用生成的本地配置启动（不会改你 Git 里的 `config.yaml`）：
   ```bash
   MIDAS_CONFIG_PATH=.tmp/config.xhs.local.yaml uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```
4. 先用小 `limit`（如 3）并传 `confirm_live=true` 试跑。
5. 观察是否返回 `AUTH_EXPIRED` 或 `RATE_LIMITED`，再调整。

详细步骤见：`XHS_WEB_READONLY_SETUP.md`

## API examples

```bash
curl http://127.0.0.1:8000/health
```

```bash
curl -X POST http://127.0.0.1:8000/api/bilibili/summarize \
  -H 'Content-Type: application/json' \
  -d '{"video_url":"https://www.bilibili.com/video/BV1xx411c7mD"}'
```

```bash
curl -X POST http://127.0.0.1:8000/api/xiaohongshu/sync \
  -H 'Content-Type: application/json' \
  -d '{"limit":5}'
```

```bash
# 创建异步任务
curl -X POST http://127.0.0.1:8000/api/xiaohongshu/sync/jobs \
  -H 'Content-Type: application/json' \
  -d '{"limit":5}'

# 查询任务进度
curl http://127.0.0.1:8000/api/xiaohongshu/sync/jobs/<job_id>
```

```bash
# web_readonly 模式（真实请求）需显式确认
curl -X POST http://127.0.0.1:8000/api/xiaohongshu/sync/jobs \
  -H 'Content-Type: application/json' \
  -d '{"limit":3,"confirm_live":true}'
```

## Notes

- Default ASR mode is `mock` for local development.
- To use real ASR, install `faster-whisper` and set `asr.mode: faster_whisper`.
- To use real LLM output, set `llm.enabled: true` and configure API params.
- Current Xiaohongshu integration mode is `mock` to validate workflow and risk controls.
- Synced note IDs persist in `xiaohongshu.db_path` (default `.tmp/midas.db`).
- `web_readonly` 模式仍属于非官方接口回放，务必低频、低并发、只读请求，优先保护账号安全。

## Tests

```bash
cd server
source .venv/bin/activate
pytest -q
```

已修复测试导入路径，`pytest` 可直接运行。

## Pre-Home Checks (No Live XHS Traffic)

```bash
cd server
source .venv/bin/activate
python tools/selfcheck.py
```

- 用于检查配置与依赖是否就绪（LLM/ASR/yt-dlp/ffmpeg/xhs 模式）。

```bash
cd server
source .venv/bin/activate
python tools/smoke_test.py --profile mock
```

- 用于做无风险接口冒烟（`/health`、B站参数校验、小红书 mock 同步与 job 轮询）。

如果服务端当前是 `web_readonly` 模式（不发真实请求，仅验证保护机制）：

```bash
python tools/smoke_test.py --profile web_guard
```

## One-Command Local Run

```bash
cd server
tools/run_local_stack.sh --profile mock
```

- 执行顺序：`selfcheck -> 启动服务 -> smoke_test`。
- 默认 `selfcheck` 失败仅告警继续；如果你想严格阻断：

```bash
tools/run_local_stack.sh --profile mock --strict-selfcheck
```

停止本地服务：

```bash
tools/stop_local_stack.sh
```
