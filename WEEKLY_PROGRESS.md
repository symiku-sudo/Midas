# Midas 周进度交接（2026-02-24）

## 本周目标

完成第一个可交付里程碑：服务端 MVP（配置、`/health`、B 站总结接口、统一错误码）。

## 已完成

- 新增服务端工程目录：`server/`
- 配置系统：`config.yaml` + `config.example.yaml`
- 统一响应结构：`ok/code/message/data/request_id`
- 请求 ID 中间件：自动读写 `X-Request-ID`
- 全局异常处理：
  - `INVALID_INPUT`
  - `AUTH_EXPIRED`
  - `RATE_LIMITED`
  - `UPSTREAM_ERROR`
  - `DEPENDENCY_MISSING`
  - `INTERNAL_ERROR`
- 已实现接口：
  - `GET /health`
  - `POST /api/bilibili/summarize`
- B 站总结链路（MVP）：
  - 链接校验
  - `yt-dlp + ffmpeg` 音频下载
  - ASR（默认 `mock`，支持切换 `faster_whisper`）
  - LLM 总结（默认关闭，开启后走 OpenAI-compatible `/chat/completions`）
- 基础测试：`2 passed`

## 本地运行

```bash
cd server
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

测试：

```bash
cd server
source .venv/bin/activate
python -m pytest -q
```

## 文件清单（本次新增）

- `server/app/main.py`
- `server/app/api/routes.py`
- `server/app/core/config.py`
- `server/app/core/errors.py`
- `server/app/core/response.py`
- `server/app/core/logging.py`
- `server/app/middleware/request_id.py`
- `server/app/models/schemas.py`
- `server/app/services/audio_fetcher.py`
- `server/app/services/asr.py`
- `server/app/services/llm.py`
- `server/app/services/bilibili.py`
- `server/tests/test_api.py`
- `server/config.yaml`
- `server/config.example.yaml`
- `server/requirements.txt`
- `server/README.md`

## 当前限制

- `asr.mode=mock` 时不会做真实语音识别（用于本地先打通流程）。
- 若启用真实链路，需要系统安装 `yt-dlp`、`ffmpeg`，并安装 `faster-whisper`。
- 小红书同步（限量/去重/延迟/熔断）尚未开发。
- Android 客户端尚未开始。

## 下次接续建议（优先级）

1. 开发小红书同步服务端（SQLite 去重 + 熔断 + 风控延迟）。
2. 固化错误码文档并补充接口集成测试。
3. 启动 Android 最小客户端（连接测试 + B 站输入和结果展示）。

## 快速检查命令

```bash
# 健康检查
curl --noproxy '*' http://127.0.0.1:8000/health

# B 站总结
curl --noproxy '*' -X POST http://127.0.0.1:8000/api/bilibili/summarize \
  -H 'Content-Type: application/json' \
  -d '{"video_url":"https://www.bilibili.com/video/BV1xx411c7mD"}'
```
