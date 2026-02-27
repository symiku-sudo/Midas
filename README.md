# Midas

个人多模态知识库助手（MVP）。

## 当前完成状态

- 服务端（FastAPI）：已完成
  - `GET /health`
  - `POST /api/bilibili/summarize`（`video_url` 支持完整链接或直接传 `BV` 号）
  - `POST /api/xiaohongshu/sync`
  - `POST /api/xiaohongshu/summarize-url`
  - `GET /api/xiaohongshu/sync/pending-count`
  - `POST /api/xiaohongshu/sync/jobs`
  - `GET /api/xiaohongshu/sync/jobs/{job_id}`
  - `POST /api/xiaohongshu/sync/jobs/{job_id}/ack`
  - `POST /api/xiaohongshu/auth/update`
- Android 客户端（Compose）：已完成最小可用版本
  - 服务端地址配置与持久化
  - 连接测试
  - B 站总结请求与 Markdown 展示
  - 小红书同步任务创建、轮询进度（x/y）与增量结果展示（成功一篇显示一篇）
  - 小红书异步任务展示后自动 ACK（展示成功再写去重）

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
tools/run_local_stack.sh --profile web_guard
```

停止服务：

```bash
cd server
tools/stop_local_stack.sh
```

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

## 说明

- 当前小红书同步默认 `web_readonly` 低风险只读模式（需显式 `confirm_live=true`，并受最小同步间隔保护）。当静态签名翻页遇到 `406` 时，会自动回退到 Playwright 实时抓取（需安装 Playwright）。
- Android 端可通过内置 WebView 登录并上传 Cookie/UA 到服务端（`/api/xiaohongshu/auth/update`），减少手工 HAR/cURL 更新频率。
- 当前默认 `llm.enabled=true`、`asr.mode=faster_whisper`、`asr.model_size=base`。
- 真实小红书网页端接口回放仍有平台风控风险，建议低频、小批量执行。
