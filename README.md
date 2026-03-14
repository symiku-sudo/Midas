# Midas

个人多模态知识库助手（MVP）。

## 当前完成状态

- 服务端（FastAPI）：已完成
  - `GET /health`
  - `GET /api/finance/signals`
  - `POST /api/jobs/bilibili-summarize|xiaohongshu/summarize-url|xiaohongshu/sync`
  - `GET /api/jobs|/api/jobs/{job_id}`
  - `POST /api/jobs/{job_id}/retry`
  - `GET /api/xiaohongshu/sync/cooldown|pending-count`
  - `GET /api/notes/search`
  - `POST /api/bilibili/summarize`（`video_url` 支持完整链接或直接传 `BV` 号）
  - `POST /api/xiaohongshu/summarize-url`
  - `POST /api/xiaohongshu/auth/update`
  - `POST /api/notes/merge/suggest|preview|commit|rollback|finalize`
- Android 客户端（Compose）：已完成最小可用版本
  - 服务端地址配置与持久化
  - 连接测试
  - 单层导航（`B站 / 小红书 / 笔记 / 资产 / 设置`）
  - B 站总结请求、任务历史与 Markdown 展示
  - 小红书单篇总结、批量同步、任务历史与结果保存
  - 资产系统面板（市场信号 + 资产总览 + 今日关注建议）
  - 资产截图识别回填（最多 5 张，端侧压缩后上传，识别后手动保存）
  - 笔记库智能合并（候选、预览、回退、确认破坏性收尾）

## 目录

- `server/`：Python 服务端
- `android/`：Android 客户端工程
- `server/API_CONTRACT.md`：服务端接口契约

## 快速开始

### 1) 启动服务端

```bash
cd server
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 2) 本地测试服务端

```bash
cd server
source .venv/bin/activate
python -m pytest -q
```

### 2.1) 一键本地启动（含自检 + 冒烟）

```bash
cd server
tools/run_local_stack.sh --profile mock
```

停止服务：

```bash
cd server
tools/stop_local_stack.sh
```

`run_local_stack.sh` 会在服务冒烟通过后自动启动/复用 `finance_signals` worker，`stop_local_stack.sh` 会一并停止该 worker。

更简化的统一入口：

```bash
cd server
tools/dev_server.sh start
tools/dev_server.sh status
tools/dev_server.sh logs 120
tools/dev_server.sh stop
```

### 2.2) 切到“可真实跑”配置（B 站链路）

```bash
cd server
cp config.real.example.yaml config.yaml
```

`config.yaml` 是本地配置文件，不纳入 Git 版本控制。

然后至少补齐：
- `llm.api_key`
- 系统命令可用：`yt-dlp`、`ffmpeg`
- Python 依赖：`faster-whisper`（当 `asr.mode=faster_whisper`）

### 2.3) 清理“未保存但已去重”的小红书 note_id

```bash
server/.venv/bin/python server/tools/prune_unsaved_synced_notes.py --dry-run --show-ids
server/.venv/bin/python server/tools/prune_unsaved_synced_notes.py --show-ids
```

### 3) 启动 Android 客户端

- 用 Android Studio 打开 `android/` 目录。
- 连接真机或模拟器运行 `app`。
- 在“设置”页填入服务端地址（如 `http://192.168.1.5:8000/`）。

### 4) 一键 release（严格自检 + mobile 重启 + 导出 APK）

```bash
tools/release.sh
```

可选参数：
- `--release`：导出 release APK（默认 debug）
- `--output <dir>`：指定导出目录
- `--name <filename.apk>`：指定导出文件名
- `--skip-build`：跳过 Gradle 构建，仅导出现有 APK
- `--share-tailnet`：额外启动 APK 分享并输出 Tailscale 下载链接
- `--share-port <port>`：分享端口（默认 `8765`）
- `--notify-ntfy`：流程完成后发送一条 ntfy 通知（best-effort）

### 5) 基于 Tailscale 自建 ntfy（内网通知）

> 说明：通知工具已拆分为子模块 `tools/ntfy-notify`；`midas/tools/ntfy_*.sh` 为代理入口。

首次拉取仓库后请初始化子模块：

```bash
git submodule update --init --recursive
```

快速初始化：

```bash
tools/ntfy_selfhost.sh init --tailnet-host <tailnet-host-or-ip> --topic midas-task
tools/ntfy_selfhost.sh install-binary   # 仅当本机没有 Docker/Compose
tools/ntfy_selfhost.sh start
```

更多命令（鉴权、Token、Android 侧操作）见：
- `tools/ntfy/README.md`

发送测试消息（复用生成的配置）：

```bash
tools/ntfy_notify.sh --config .tmp/ntfy/notify.env
```

## 说明

- 当前小红书能力为“按 URL 总结单篇”。
- 服务端异步任务中心支持任务历史、结果回看和失败/中断任务重试；历史保存在 `server/.tmp/async_jobs.json`。
- 服务端支持可选访问令牌保护：当 `server/config.yaml` 里配置 `auth.access_token` 后，客户端需带 `Authorization: Bearer <token>`。
- Android 端的 B 站/小红书面板现在都内置“最近任务”卡片，可刷新任务列表、查看成功结果，并对失败/中断任务直接重试。
- 小红书面板已补齐批量同步：可查看待同步数量、冷却状态、提交后台同步任务，并把当前结果一键批量保存到笔记库。
- Android 财经面板现在会按动作类型分组显示 `focus_cards`，并支持端侧“已处理/恢复全部”闭环；Top5 新闻默认先展示 3 条，减少首屏信息量。
- Finance Signals 现在会把 Top5 新闻和 watchlist 标的做一层关联：新闻卡会显示“影响哪些关注项”，Watchlist 行会显示“最近关联新闻数”和命中关键词。
- Finance Signals 还会返回第一版“今日关注建议”，把阈值触发和影响到 watchlist 的新闻整理成优先级更高的关注卡片，并附上建议动作。
- 这些关注建议现在也带结构化 `action_type/reasons`，后面继续做筛选、排序和自动化动作时不用再从自然语言里反推。
- Android 端左上角可切换“笔记系统 / 资产系统”；资产系统分为两屏：`Watchlist+新闻` 与 `资产统计`。
- `Watchlist+新闻` 面板会在资产系统打开时自动轮询刷新；若新闻拉取超过阈值未更新，会显示“数据可能陈旧”提示。
- Watchlist 行会显式展示监控阈值标签；当阈值触发时，标签颜色会切到高亮态，不再把行情警报混进新闻板块。
- 面板会额外展示“24小时新闻摘要”，改为按钮触发；若距离上次真实生成不足 3 小时，会直接复用上次结果，避免重复占用 token。
- 新闻面板现为“今日金融与时政新闻 Top5”，按发布时间衰减、来源权重、主题关键词和跨源覆盖综合排序，并对同主题标题去重。
- RSS 新闻不再触发 ntfy；Watchlist 行情 ntfy 只发送真正的阈值触发，不发送抓取异常/空数据类告警，并可在客户端直接切换开关。
- `资产统计` 采用“万元人民币”单位，按风险从高到低展示分类（股票、股票基金、黄金、债券/债券基金、货币基金、银行定期存款、银行活期存款、公积金）。
- 支持一键复制资产概况文本（可直接粘贴给大模型咨询资产配置问题）。
- `资产统计` 的当前金额和历史快照现在都由服务端持久化；Android 会优先读取服务端数据，并在首次连上服务端时把旧版本遗留的本地当前值/历史快照自动迁移上去。
- 服务端会后台定期备份 SQLite 数据库到 `server/.tmp/backups/`，同时保留原有的“保存后立即备份”；默认保留 `midas_latest.db` 加最近 `10` 份时间戳备份。
- B站/小红书新生成摘要会额外附带“评论区洞察（含点赞权重）”章节（best-effort）。
- 每次新增已保存笔记（B站/小红书）后，服务端会自动备份一次数据库（位于 `server/.tmp/backups/`）。
- Android 端可通过内置 WebView 登录并上传 Cookie/UA 到服务端（`/api/xiaohongshu/auth/update`），减少手工 HAR/cURL 更新频率。
- 当前默认 `llm.enabled=true`、`asr.mode=faster_whisper`、`asr.model_size=base`。
- 智能合并候选可启用本地 embedding 语义相似（`server/config.yaml` 的 `notes_merge.*`）。
- merged 笔记正文末尾会自动追加“原始笔记来源”（原始标题 + 可点击链接）。
- 笔记库接口返回的 `saved_at` 统一按东八区（UTC+08:00）显示。
- 真实小红书网页端接口回放仍有平台风控风险，建议低频、小批量执行。
