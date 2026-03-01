# Midas Server (MVP - Week 2)

## What is implemented

- `GET /health`
- `POST /api/bilibili/summarize`
- `POST /api/notes/bilibili/save`
- `GET /api/notes/bilibili`
- `DELETE /api/notes/bilibili/{note_id}` / `DELETE /api/notes/bilibili`
- `POST /api/xiaohongshu/summarize-url`
- `POST /api/notes/xiaohongshu/save-batch`
- `GET /api/notes/xiaohongshu`
- `DELETE /api/notes/xiaohongshu/{note_id}` / `DELETE /api/notes/xiaohongshu`
- `POST /api/notes/xiaohongshu/synced/prune`
- `POST /api/notes/merge/suggest`
- `POST /api/notes/merge/preview`
- `POST /api/notes/merge/commit`
- `POST /api/notes/merge/rollback`
- `POST /api/notes/merge/finalize`
- `POST /api/xiaohongshu/capture/refresh`
- `POST /api/xiaohongshu/auth/update`
- `GET /api/config/editable`
- `PUT /api/config/editable`
- `POST /api/config/editable/reset`
- Unified response envelope: `ok/code/message/data/request_id`
- Unified error handling and request-id middleware
- Config-driven runtime (`config.yaml`)
- Xiaohongshu URL summarize + dedupe(SQLite)
- Xiaohongshu 视频笔记总结：音频导出 -> ASR -> LLM（合并正文）
- API schema reference: `API_CONTRACT.md`

## Quick start

```bash
cd server
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## WSL one-script workflow

```bash
cd server
tools/dev_server.sh start
tools/dev_server.sh status
tools/dev_server.sh logs 120
tools/dev_server.sh stop
```

## Clean temp files (`server/.tmp`)

```bash
cd server
tools/clean_tmp.sh
```

- 默认会清空 `server/.tmp` 下所有内容（含 `midas.db`、日志、PID、临时音频）。
- 若需保留小红书去重状态数据库：`tools/clean_tmp.sh --keep-db`。
- 若服务正在运行，脚本默认会拒绝清理；可先 `tools/dev_server.sh stop`。

## Prune unsaved synced note IDs

当去重表里有“未保存到笔记库”的小红书 `note_id` 时，可批量清理：

```bash
server/.venv/bin/python server/tools/prune_unsaved_synced_notes.py --show-ids
```

也可直接通过 API 执行正式清理（非 dry-run）：

```bash
curl -X POST http://127.0.0.1:8000/api/notes/xiaohongshu/synced/prune
```

仅预览不删除：

```bash
server/.venv/bin/python server/tools/prune_unsaved_synced_notes.py --dry-run --show-ids
```

## Refresh XHS auth config

若 `config.yaml` 已配置默认抓包路径，可直接刷新 auth 配置：
- 优先读取 `xiaohongshu.web_readonly.har_capture_path`
- HAR 不可用时回退 `xiaohongshu.web_readonly.curl_capture_path`

```bash
curl -X POST http://127.0.0.1:8000/api/xiaohongshu/capture/refresh
```

注意：
- 若 HAR 不包含 `Cookie`（常见于脱敏导出），接口会返回 `400`。
- 若 HAR 不可用，会自动尝试 `curl_capture_path` 指向的 cURL 文件。
- 两者都不含 Cookie 时会失败，请重新导出“包含敏感数据”的 HAR/cURL。

也支持由移动端直接上传登录态（Cookie/UA）：

```bash
curl -X POST http://127.0.0.1:8000/api/xiaohongshu/auth/update \
  -H 'Content-Type: application/json' \
  -d '{"cookie":"a=1; b=2","user_agent":"Mozilla/5.0 (Linux; Android 14)","origin":"https://www.xiaohongshu.com","referer":"https://www.xiaohongshu.com/"}'
```

## Real-run config (Bilibili path)

```bash
cd server
cp config.real.example.yaml config.yaml
```

`config.yaml` 是本地运行配置，默认不纳入 Git 版本控制。

可用以下命令校验 `config.yaml` 与 `config.example.yaml` 的键结构是否一致（只允许 value 不同）：

```bash
cd server
python tools/check_config_keys.py
```

Then fill:
- `llm.api_key`
- Ensure `yt-dlp` and `ffmpeg` are installed on system
- Install `faster-whisper` if `asr.mode=faster_whisper`

## Safe live mode (Xiaohongshu, read-only)

服务端支持 `xiaohongshu.mode=web_readonly` 的低风险只读模式：
- 只允许 `GET/POST` 单请求回放
- 强制 HTTPS + 域名白名单
- `page_fetch_driver=auto` 时会在静态签名翻页遇到 `406` 后自动切换 Playwright 实时抓取

若使用 `auto/playwright`，需安装 Playwright 依赖与浏览器：

```bash
pip install playwright
python -m playwright install chromium
```

建议流程：
1. 在浏览器 DevTools 里抓“小红书收藏列表”请求。
2. 用脚本自动把抓包写入 `server/.env`（避免手填出错）：
   ```bash
   cd server
   python tools/xhs_capture_to_config.py --har /path/to/capture.har
   ```
3. 正常启动服务即可（`config.yaml` 会读取 `.env` 里的 `XHS_*` 变量）：
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```
4. 先用 1-2 条真实 URL 试跑。
5. 观察是否返回 `AUTH_EXPIRED` 或 `RATE_LIMITED`，再调整。

详细步骤见：`XHS_WEB_READONLY_SETUP.md`

## API examples

```bash
curl http://127.0.0.1:8000/health
```

```bash
curl -X POST http://127.0.0.1:8000/api/bilibili/summarize \
  -H 'Content-Type: application/json' \
  -d '{"video_url":"BV1xx411c7mD"}'
```

- `video_url` 支持完整链接，也支持直接传 `BV` 号（服务端会自动补全前缀）。

```bash
# 手动保存一次 B 站总结
curl -X POST http://127.0.0.1:8000/api/notes/bilibili/save \
  -H 'Content-Type: application/json' \
  -d '{"video_url":"https://www.bilibili.com/video/BV1xx411c7mD","summary_markdown":"# 总结","elapsed_ms":123,"transcript_chars":456}'

# 查看 B 站已保存笔记
curl http://127.0.0.1:8000/api/notes/bilibili
```

```bash
# 按 URL 总结单篇小红书笔记
curl -X POST http://127.0.0.1:8000/api/xiaohongshu/summarize-url \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://www.xiaohongshu.com/explore/xxxxxx"}'
```

```bash
# 批量保存小红书总结结果（notes 数组元素结构与 /api/xiaohongshu/summarize-url 返回一致）
curl -X POST http://127.0.0.1:8000/api/notes/xiaohongshu/save-batch \
  -H 'Content-Type: application/json' \
  -d '{"notes":[{"note_id":"mock-note-001","title":"示例","source_url":"https://www.xiaohongshu.com/explore/mock-note-001","summary_markdown":"# 总结"}]}'

# 查看小红书已保存笔记
curl http://127.0.0.1:8000/api/notes/xiaohongshu
```

```bash
# 获取智能合并候选
curl -X POST http://127.0.0.1:8000/api/notes/merge/suggest \
  -H 'Content-Type: application/json' \
  -d '{"source":"bilibili","limit":20,"min_score":0.35}'

# 生成合并预览
curl -X POST http://127.0.0.1:8000/api/notes/merge/preview \
  -H 'Content-Type: application/json' \
  -d '{"source":"bilibili","note_ids":["note_a","note_b"]}'

# 提交合并（默认保留原笔记）
curl -X POST http://127.0.0.1:8000/api/notes/merge/commit \
  -H 'Content-Type: application/json' \
  -d '{"source":"bilibili","note_ids":["note_a","note_b"]}'

# 回退该次合并
curl -X POST http://127.0.0.1:8000/api/notes/merge/rollback \
  -H 'Content-Type: application/json' \
  -d '{"merge_id":"merge_xxx"}'

# 确认合并结果（破坏性：删除原笔记）
curl -X POST http://127.0.0.1:8000/api/notes/merge/finalize \
  -H 'Content-Type: application/json' \
  -d '{"merge_id":"merge_xxx","confirm_destructive":true}'
```

```bash
# 读取可编辑配置（排除 api_key/cookie 等敏感项）
curl http://127.0.0.1:8000/api/config/editable

# 更新部分配置
curl -X PUT http://127.0.0.1:8000/api/config/editable \
  -H 'Content-Type: application/json' \
  -d '{"settings":{"xiaohongshu":{"default_limit":8},"runtime":{"log_level":"DEBUG"}}}'

# 恢复默认（v0.1 基线）
curl -X POST http://127.0.0.1:8000/api/config/editable/reset
```

## Notes

- Default ASR mode is `faster_whisper` with `asr.model_size=base`.
- Default LLM mode is enabled (`llm.enabled=true`); set `llm.api_key` before real run.
- Default Xiaohongshu integration mode is `web_readonly`.
- Synced note IDs persist in `xiaohongshu.db_path` (default `.tmp/midas.db`).
- 单篇 URL 总结成功后会自动把 `note_id` 写入去重表。
- 删除“已保存小红书笔记”不会删除去重表中的 `note_id`，后续按 URL 总结仍会复用已处理状态。
- 每次新增 B 站或小红书已保存笔记后，服务会自动备份一次数据库到 `.tmp/backups/`。
- 智能合并默认非破坏，`finalize` 后会做破坏性清理（仅保留 merged 笔记）。
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

- 用于做无风险接口冒烟（`/health`、B站参数校验、小红书 `summarize-url` mock 检查）。

如果服务端当前是 `web_readonly` 模式，仍可沿用同一命令做基础可用性检查：

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
