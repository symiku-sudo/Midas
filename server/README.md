# Midas Server (MVP - Week 2)

## What is implemented

- `GET /health`
- `GET /api/home/overview`
- `GET /api/finance/signals`
- `GET /api/finance/signals/history`
- `POST /api/finance/signals/cards/{card_id}/status`
- `POST /api/assets/fill-from-images`
- `GET /api/assets/current`
- `PUT /api/assets/current`
- `GET /api/assets/snapshots`
- `POST /api/assets/snapshots`
- `DELETE /api/assets/snapshots/{record_id}`
- `POST /api/jobs/bilibili-summarize`
- `POST /api/jobs/xiaohongshu/summarize-url`
- `GET /api/jobs`
- `GET /api/jobs/{job_id}`
- `POST /api/jobs/{job_id}/retry`
- `POST /api/bilibili/summarize`
- `POST /api/notes/bilibili/save`
- `GET /api/notes/bilibili`
- `GET /api/notes/search`
- `GET /api/notes/review/topics`
- `GET /api/notes/review/timeline`
- `GET /api/notes/{source}/{note_id}/related`
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
- 新生成摘要自动追加“评论区洞察（含点赞权重）”章节（B站/小红书，best-effort）
- API schema reference: `API_CONTRACT.md`

## Quick start

```bash
cd server
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

如需启用轻量访问保护，可在 `config.yaml` 中设置：

```yaml
auth:
  access_token: "your-token"
```

启用后，除 `/health` 外的接口都需要带：

```bash
Authorization: Bearer your-token
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

## Async Jobs

服务端现在提供第一版单进程异步任务中心，用于把长耗时总结任务放到后台执行，并把历史持久化到 `server/.tmp/async_jobs.json`。

当前支持：
- `POST /api/jobs/bilibili-summarize`
- `POST /api/jobs/xiaohongshu/summarize-url`
- `GET /api/jobs`
- `GET /api/jobs/{job_id}`
- `POST /api/jobs/{job_id}/retry`

行为说明：
- 旧同步接口 `POST /api/bilibili/summarize` 和 `POST /api/xiaohongshu/summarize-url` 仍保留，现有客户端不受影响。
- 新异步任务接口会立即返回 `job_id`，由后台 worker 顺序执行。
- 服务重启后，已完成/失败历史会保留；启动时仍处于 `RUNNING` 的任务会被标记为 `INTERRUPTED`，避免假状态残留。
- 重试任务会在响应和历史列表里携带 `retry_of_job_id`，便于客户端回溯来源。
- 当前仅允许重试 `FAILED` / `INTERRUPTED` 状态的任务，重试时会复用原请求体创建新任务。

## Finance Signals Worker

用于持续生成前端 `Finance Signals` 面板需要的本地状态文件（默认 `server/finance_signals/finance_status.json`），并由 `GET /api/finance/signals` 提供给客户端：

```bash
cd server
tools/finance_signals.sh start
tools/finance_signals.sh status
tools/finance_signals.sh check
tools/finance_signals.sh logs 120
tools/finance_signals.sh stop
```

说明：
- 运行参数全部来自 `finance_signals/financial_config.yaml`。
- `check` 会校验 `finance_status.json` 是否存在且更新时间未过期（阈值由 `runtime.health_max_staleness_seconds` 控制）。
- 新闻面板现已输出“今日金融与时政新闻 Top5”，默认过滤 24 小时外旧新闻。
- “过去 24 小时新闻摘要”改为客户端按钮触发；Worker 只维护新闻候选与 Top5，不再自动占用 LLM。
- 排序采用新闻客户端常见因子：发布时间衰减、来源权重、主题关键词、跨源覆盖加权，再做同主题去重。
- API 服务端会在读取状态文件时，把 Top5 新闻与 watchlist 标的做一层关联归并；默认别名配置写在 `finance_signals/financial_config.yaml` 的 `market_data.instruments[].aliases`。
- 客户端可直接显示“某条新闻可能影响哪些关注标的”以及“某个标的最近关联了几条新闻”。
- API 服务端还会返回第一版 `focus_cards`，把“阈值触发”和“影响到 watchlist 的新闻”整理成今日关注建议，并附上 `action_label/action_hint` 说明下一步建议动作。
- `focus_cards` 现在还带结构化 `action_type/reasons`，并新增 `card_id/status/status_updated_at/handled_at`，用于服务端持久化“已看过 / 今日忽略 / 保持关注 / 取消忽略”。
- Finance Signals 历史可通过 `GET /api/finance/signals/history` 回看；客户端可通过 `POST /api/finance/signals/cards/{card_id}/status` 直接更新状态。
- watchlist / top_news / focus_cards 现在都会补充 `related_asset_categories/exposure_amount_wan/exposure_relevance/portfolio_impact_summary`，把新闻和 watchlist 信号与当前资产暴露关联起来。
- 可通过 `news.filters.source_allowlist/source_blocklist/domain_allowlist/domain_blocklist` 做来源白名单/黑名单控制。
- 可通过 `news.digest.max_items/max_summary_chars_per_item/prompt_char_limit/reuse_within_seconds` 控制摘要样本数、单条摘要截断长度、单次 prompt 文本长度上限，以及“3 小时内复用上次摘要”的窗口。
- 可通过 `market_data.alerting.*` 配置 Watchlist 行情阈值告警；其状态会写入 `market_alert_debug`。
- Watchlist ntfy 仅针对真正的阈值触发发送通知，`抓取异常/行情拉取为空/缺少收盘价` 只会留在面板，不会推送。
- Watchlist ntfy 开关可通过 `PUT /api/finance/signals/watchlist-ntfy` 动态切换，worker 会在下一个轮询周期自动生效。
- 新闻摘要可通过 `POST /api/finance/signals/digest` 触发；Worker 会持续保留最近一次摘要结果，不会在后续轮询中覆盖为空。
- Worker 会额外写出 `news_last_fetch_time`、`news_stale`（由 API 服务端计算）、`news_debug.entries_scanned/matched_entries_count/top_news_count/top_unmatched_titles/digest_item_count/digest_prompt_chars/digest_status/digest_last_generated_at`，便于定位召回漏检并观察摘要 prompt 长度。

## Notes Review

- `GET /api/notes/search` 现在支持 `saved_from/saved_to/merged/sort_by/sort_order`，返回项会额外包含 `merge_state/merge_id/canonical_note_id/is_merged/topics`。
- `GET /api/notes/review/topics` 用于“最近一周 / 最近一月”主题回顾。
- `GET /api/notes/review/timeline` 用于按时间桶回看新增笔记。
- `GET /api/notes/{source}/{note_id}/related` 用于独立回查相似/相关笔记，不强制进入 merge。

## Periodic DB backup

服务端现在会在后台定期备份 SQLite 数据库到 `server/.tmp/backups/`。默认配置：

```yaml
runtime:
  backup:
    enabled: true
    interval_seconds: 21600
    startup_delay_seconds: 30
    keep_latest_files: 10
```

说明：
- 仍保留“保存成功后立即备份”的原有行为。
- 周期备份是额外兜底，主要覆盖“长时间无写入、但希望保留近期副本”的场景。
- 实际数据库路径来自 `xiaohongshu.db_path`；默认是 `server/.tmp/midas.db`。
- 若配置里使用相对路径（例如 `.tmp/midas.db`），会固定按 `server/` 目录解析，不受启动时当前工作目录影响。
- `keep_latest_files` 只统计时间戳备份文件；`midas_latest.db` 始终保留。

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
- Install `sentence-transformers` if you enable local semantic merge scoring (`notes_merge.semantic_similarity_enabled=true`)

可选：若要在 CPU 环境启用本地 embedding 语义相似，建议先装 CPU 版 torch 再装 sentence-transformers：

```bash
pip install --index-url https://download.pytorch.org/whl/cpu torch==2.5.1+cpu
pip install sentence-transformers
```

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
1. 在浏览器 DevTools 里抓一个已登录的小红书网页请求；最常见的是“收藏列表”请求，用来提取认证头。
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
# 读取 Finance Signals 面板状态
curl http://127.0.0.1:8000/api/finance/signals
```

```bash
# 上传资产截图（最多 5 张）并返回分类汇总（单位：万元人民币）
curl -X POST http://127.0.0.1:8000/api/assets/fill-from-images \
  -F "images=@/path/to/asset-1.jpg" \
  -F "images=@/path/to/asset-2.png"
```

```bash
# 读取当前资产金额（服务端持久化）
curl http://127.0.0.1:8000/api/assets/current
```

```bash
# 保存当前资产金额（不会追加历史快照）
curl -X PUT http://127.0.0.1:8000/api/assets/current \
  -H 'Content-Type: application/json' \
  -d '{
    "total_amount_wan": 15.5,
    "amounts": {
      "stock": 12.0,
      "gold": 3.5
    }
  }'
```

```bash
# 读取资产历史快照（服务端持久化）
curl http://127.0.0.1:8000/api/assets/snapshots
```

```bash
# 保存一条资产历史快照
curl -X POST http://127.0.0.1:8000/api/assets/snapshots \
  -H 'Content-Type: application/json' \
  -d '{
    "id":"asset-history-1",
    "saved_at":"2026-03-08 14:40:00",
    "total_amount_wan":15.5,
    "amounts":{"stock":12.0,"gold":3.5}
  }'
```

```bash
curl -X POST http://127.0.0.1:8000/api/bilibili/summarize \
  -H 'Content-Type: application/json' \
  -d '{"video_url":"BV1xx411c7mD"}'
```

- `video_url` 支持完整链接，也支持直接传 `BV` 号（服务端会自动补全前缀）。

```bash
# 以异步任务方式提交 B 站总结，立即返回 job_id
curl -X POST http://127.0.0.1:8000/api/jobs/bilibili-summarize \
  -H 'Content-Type: application/json' \
  -d '{"video_url":"BV1xx411c7mD"}'

# 查看最近任务历史
curl 'http://127.0.0.1:8000/api/jobs?limit=20'

# 查看单个任务状态和结果
curl http://127.0.0.1:8000/api/jobs/<job_id>

# 重试失败或中断的任务
curl -X POST http://127.0.0.1:8000/api/jobs/<job_id>/retry
```

```bash
# 手动保存一次 B 站总结
curl -X POST http://127.0.0.1:8000/api/notes/bilibili/save \
  -H 'Content-Type: application/json' \
  -d '{"video_url":"https://www.bilibili.com/video/BV1xx411c7mD","summary_markdown":"# 总结","elapsed_ms":123,"transcript_chars":456}'

# 查看 B 站已保存笔记
curl http://127.0.0.1:8000/api/notes/bilibili

# 统一检索全部已保存笔记
curl 'http://127.0.0.1:8000/api/notes/search?keyword=%E7%BE%8E%E8%81%94%E5%82%A8&limit=20'
```

```bash
# 按 URL 总结单篇小红书笔记
curl -X POST http://127.0.0.1:8000/api/xiaohongshu/summarize-url \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://www.xiaohongshu.com/explore/xxxxxx"}'
```

```bash
# 以异步任务方式提交小红书单篇总结
curl -X POST http://127.0.0.1:8000/api/jobs/xiaohongshu/summarize-url \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://www.xiaohongshu.com/explore/xxxxxx"}'
```

```bash
# 保存小红书总结结果（notes 数组可传单条或多条，元素结构与 /api/xiaohongshu/summarize-url 返回一致）
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

# 如需显示中相关（WEAK）候选，显式开启 include_weak
curl -X POST http://127.0.0.1:8000/api/notes/merge/suggest \
  -H 'Content-Type: application/json' \
  -d '{"source":"bilibili","limit":20,"min_score":0.35,"include_weak":true}'

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
- Synced note IDs persist in `xiaohongshu.db_path` (default `.tmp/midas.db`, resolved under `server/`).
- Async job history persists in `.tmp/async_jobs.json` (resolved under `server/`).
- 单篇 URL 总结成功后会自动把 `note_id` 写入去重表。
- 删除“已保存小红书笔记”不会删除去重表中的 `note_id`，后续按 URL 总结仍会复用已处理状态。
- 每次新增 B 站或小红书已保存笔记后，服务会自动备份一次数据库到 `.tmp/backups/`。
- B站/小红书新生成 `summary_markdown` 会附加“`## 评论区洞察（含点赞权重）`”章节；评论抓取失败时仅降级该章节，不影响主摘要。
- 智能合并默认非破坏，`finalize` 后会做破坏性清理（仅保留 merged 笔记）。
- 合并候选评分支持本地 embedding 语义相似（配置见 `notes_merge.*`，可关闭后回退词面相似）。
- merged 笔记正文末尾会自动追加 `原始笔记来源` 小节（原始标题 + 可点击来源链接）。
- 笔记库返回的 `saved_at` 统一按东八区（UTC+08:00）显示。
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
- 执行顺序：`selfcheck -> 启动服务 -> smoke_test -> 启动/复用 finance_signals worker`。
- 默认 `selfcheck` 失败仅告警继续；如果你想严格阻断：

```bash
tools/run_local_stack.sh --profile mock --strict-selfcheck
```

停止本地服务：

```bash
tools/stop_local_stack.sh
```

- `stop_local_stack.sh` 会同时停止 `uvicorn` 与 `finance_signals` worker。
