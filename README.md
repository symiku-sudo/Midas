# Midas

个人多模态知识库助手（MVP）。

## 当前完成状态

- 服务端（FastAPI）：已完成
  - `GET /health`
  - `POST /api/bilibili/summarize`
  - `POST /api/xiaohongshu/sync`
  - `POST /api/xiaohongshu/sync/jobs`
  - `GET /api/xiaohongshu/sync/jobs/{job_id}`
- Android 客户端（Compose）：已完成最小可用版本
  - 服务端地址配置与持久化
  - 连接测试
  - B 站总结请求与 Markdown 展示
  - 小红书同步任务创建、轮询进度（x/y）与结果展示

## 目录

- `server/`：Python 服务端
- `android/`：Android 客户端工程
- `WEEKLY_PROGRESS.md`：阶段交接与后续建议

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

然后至少补齐：
- `llm.api_key`
- 系统命令可用：`yt-dlp`、`ffmpeg`
- Python 依赖：`faster-whisper`（当 `asr.mode=faster_whisper`）

### 3) 启动 Android 客户端

- 用 Android Studio 打开 `android/` 目录。
- 连接真机或模拟器运行 `app`。
- 在“设置”页填入服务端地址（如 `http://192.168.1.5:8000/`）。

## 说明

- 当前小红书同步默认 `web_readonly` 低风险只读模式（需显式 `confirm_live=true`，并受最小同步间隔保护）。
- 当前默认 `llm.enabled=true`、`asr.mode=faster_whisper`、`asr.model_size=base`。
- 真实小红书网页端接口回放仍有平台风控风险，建议低频、小批量执行。
