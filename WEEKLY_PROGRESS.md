# Midas 周进度交接（2026-02-24）

## 里程碑状态

- Week 1：服务端 MVP 基线（B 站总结） -> 已完成
- Week 2：服务端小红书同步链路（限量/去重/熔断） -> 已完成
- Week 3：服务端进度任务机制 + Android 客户端最小可用版 -> 已完成

## Week 3 新增完成项

### 服务端

- 新增小红书同步异步任务接口：
  - `POST /api/xiaohongshu/sync/jobs`
  - `GET /api/xiaohongshu/sync/jobs/{job_id}`
- 新增任务管理器：
  - 任务状态：`pending/running/succeeded/failed`
  - 进度字段：`current/total/message`
  - 失败结构：`error.code/error.message/error.details`
- 小红书同步服务支持进度回调（可实时回传 x/y）
- API 契约文档已更新：`server/API_CONTRACT.md`
- 服务端测试新增 2 条（任务进度 + job not found）

### Android 客户端

- 新建完整 Android 工程：`android/`
- 完成三个页面：
  - 设置页：服务端地址保存 + 连接测试
  - B 站页：提交链接 + 加载态 + Markdown 结果展示
  - 小红书页：创建同步任务 + 轮询进度（x/y）+ 结果展示
- 已实现 Markdown 渲染组件（Markwon）
- 客户端文档：`android/README.md`

## 当前可用接口

- `GET /health`
- `POST /api/bilibili/summarize`
- `POST /api/xiaohongshu/sync`
- `POST /api/xiaohongshu/sync/jobs`
- `GET /api/xiaohongshu/sync/jobs/{job_id}`

## 验证结果

- 服务端自动化测试：`7 passed`
- Python 编译检查：通过（`python -m compileall app`）

## 本地运行

### 服务端

```bash
cd server
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

```bash
cd server
source .venv/bin/activate
python -m pytest -q
```

### Android

- Android Studio 打开 `android/`
- 运行 `app` 模块
- 设置服务端地址后测试连接

## 当前限制

- 小红书真实网页端接口尚未接入，当前 `xiaohongshu.mode` 默认为 `mock`。
- Android 构建未在当前环境执行（本机无 Gradle/Android SDK CLI），需在 Android Studio 中同步构建验证。

## 下阶段建议

1. 接入小红书真实数据源（保留已完成的任务进度与熔断框架）。
2. 增加 Android 仪表化测试与 UI 回归用例。
3. 迁移到 GPU 环境，完成 ASR 高精度参数调优（阶段 7）。
