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

### 3) 启动 Android 客户端

- 用 Android Studio 打开 `android/` 目录。
- 连接真机或模拟器运行 `app`。
- 在“设置”页填入服务端地址（如 `http://192.168.1.5:8000/`）。

## 说明

- 当前小红书同步默认 `mock` 数据模式，用于验证风控流程（限量、去重、熔断与进度回传）。
- 真实小红书网页端接口接入时，可复用现有同步任务与进度查询框架。
