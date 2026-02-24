# Midas 周进度交接（2026-02-24）

## 里程碑状态

- Week 1 目标：服务端 MVP 基线（B 站总结） -> 已完成
- Week 2 目标：服务端小红书同步链路（限量/去重/熔断） -> 已完成

## 本周（Week 2）新增完成项

- 新增接口：`POST /api/xiaohongshu/sync`
- 新增小红书同步服务能力：
  - 单次 `limit` 限制（受 `max_limit` 约束）
  - SQLite 持久化去重（已同步 note_id 不重复处理）
  - 连续失败熔断（`circuit_breaker_failures` 阈值）
  - 统一错误码返回（包含 `CIRCUIT_OPEN`）
- 新增小红书配置段：`xiaohongshu.*`
- 新增本地 mock 数据源：
  - 默认内置 5 条示例笔记
  - 支持 `mock_notes_path` 指定外部 JSON
- 扩展 LLM 服务：支持单条小红书笔记总结
- 测试补齐：
  - API 测试：首次同步、二次去重、limit 超限校验
  - 服务测试：熔断触发路径
  - 当前结果：`5 passed`

## 当前可用接口

- `GET /health`
- `POST /api/bilibili/summarize`
- `POST /api/xiaohongshu/sync`

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

## 快速检查命令

```bash
# 健康检查
curl --noproxy '*' http://127.0.0.1:8000/health

# B 站总结
curl --noproxy '*' -X POST http://127.0.0.1:8000/api/bilibili/summarize \
  -H 'Content-Type: application/json' \
  -d '{"video_url":"https://www.bilibili.com/video/BV1xx411c7mD"}'

# 小红书同步（mock）
curl --noproxy '*' -X POST http://127.0.0.1:8000/api/xiaohongshu/sync \
  -H 'Content-Type: application/json' \
  -d '{"limit":5}'
```

## 当前限制（未完成项）

- 小红书真实网页端接口尚未接入，当前 `xiaohongshu.mode` 仅支持 `mock`。
- mock 模式用于验证业务流程，不代表真实风控效果。
- Android 客户端尚未开始。

## 下周接续建议（优先级）

1. 接入小红书真实数据源（保持现有去重/熔断框架不变）。
2. 为小红书同步补“鉴权失效”和“限流”场景测试。
3. 启动 Android 最小客户端：设置页 + 连接测试 + B 站结果展示。
