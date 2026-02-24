# Midas 周进度交接（2026-02-24）

## 里程碑状态

- Week 1：服务端 MVP 基线（B 站总结） -> 已完成
- Week 2：服务端小红书同步链路（限量/去重/熔断） -> 已完成
- Week 3：服务端进度任务机制 + Android 客户端最小可用版 -> 已完成
- Week 4：小红书低风控只读模式（web_readonly）与确认开关 -> 已完成
- Week 5：抓包自动转配置 + 测试开箱即跑 -> 已完成

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
- 新增真实运行配置模板：`server/config.real.example.yaml`

## Week 4 新增完成项

### 小红书低风控增强（服务端）

- 新增 `xiaohongshu.mode=web_readonly`：
  - 仅允许 HTTPS
  - 域名白名单校验
  - 仅支持 GET/POST 请求回放
  - 最小真实同步间隔保护（默认 1800 秒）
- 新增强制确认参数：`confirm_live=true`
  - 未显式确认时拒绝真实同步请求
- 新增运行态存储：
  - 记录 `last_live_sync_ts`，用于限频保护

### 客户端联动

- Android 小红书页新增“确认真实同步请求”开关（对应 `confirm_live`）。
- 同步任务创建时自动携带 `confirm_live` 参数。

### 测试

- 服务端测试扩展到 `10 passed`：
  - web_readonly 未确认拦截
  - web_readonly 限频保护
  - web_readonly 成功后写入同步时间

## Week 5 新增完成项

### 小红书抓包提效

- 新增工具脚本：`server/tools/xhs_capture_to_config.py`
  - 支持从 HAR 自动识别小红书列表接口并生成 `web_readonly` 配置
  - 支持从 cURL + 响应 JSON 生成配置
  - 默认输出到 `server/.tmp/config.xhs.local.yaml`（避免污染仓库配置）
- 新增单测：`server/tests/test_xhs_capture_to_config.py`
  - 覆盖 cURL 解析、HAR 选择、字段推断与配置合并

### 测试可运行性修复

- 新增 `server/tests/conftest.py`，修复 `pytest` 的导入路径问题
- 现在可直接执行：
  - `cd server && source .venv/bin/activate && pytest -q`
- 当前测试结果：`14 passed`

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
