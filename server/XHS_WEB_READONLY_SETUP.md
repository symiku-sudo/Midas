# 小红书 `web_readonly` 配置步骤（低风控）

## 目标

在不做自动化登录、不做高频抓取的前提下，使用你浏览器当前登录会话里的“收藏列表请求”进行只读同步。

## 强安全原则

1. 只读：仅请求列表接口，不做写操作。
2. 低频：每次只拉少量（建议 3-10 条），并保持较长间隔。
3. 显式确认：仅在你主动勾选 `confirm_live` 时发真实请求。

## 步骤 1：准备配置

```bash
cd server
cp config.real.example.yaml config.yaml
```

先保持：
- `xiaohongshu.mode: web_readonly`
- `xiaohongshu.min_live_sync_interval_seconds: 1800`

## 步骤 2：从浏览器抓“收藏列表”请求

1. 打开小红书网页版收藏页（你已登录）。
2. 打开 DevTools -> Network。
3. 过滤 `fetch/xhr`，刷新页面。
4. 找到“收藏列表”相关请求（通常返回 JSON 列表）。
5. 记录：
   - Request URL
   - Method（GET/POST）
   - 关键请求头（至少 Cookie，可能还需要 X-S、X-T、Referer、User-Agent）
   - 若是 POST，记录请求体。

## 步骤 3：写入 `config.yaml`

示例（按实际抓到的值替换）：

```yaml
xiaohongshu:
  mode: web_readonly
  min_live_sync_interval_seconds: 1800
  web_readonly:
    request_url: "https://www.xiaohongshu.com/api/..."
    request_method: GET
    request_headers:
      Cookie: "..."
      Referer: "https://www.xiaohongshu.com/"
      User-Agent: "..."
      X-S: "..."
      X-T: "..."
    request_body: ""
    items_path: data.notes
    note_id_field: note_id
    title_field: title
    content_field_candidates: [desc, content, note_text]
    source_url_field: url
    host_allowlist: [www.xiaohongshu.com, edith.xiaohongshu.com]
```

### 可选：自动写入 `.env`（推荐）

如果你不想手填字段，可以导出 HAR 后直接生成：

```bash
cd server
python tools/xhs_capture_to_config.py --har /path/to/xhs.har
```

脚本默认写入：`server/.env` 的这些键：
- `XHS_REQUEST_URL`
- `XHS_HEADER_ACCEPT`
- `XHS_HEADER_COOKIE`
- `XHS_HEADER_ORIGIN`
- `XHS_HEADER_REFERER`
- `XHS_HEADER_USER_AGENT`
- `XHS_HEADER_X_S`
- `XHS_HEADER_X_S_COMMON`
- `XHS_HEADER_X_T`

写入后正常启动服务即可：

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

如果你只有 cURL + 响应 JSON，也可以：

```bash
python tools/xhs_capture_to_config.py \
  --curl-file /path/to/capture.curl.txt \
  --response-json /path/to/response.json
```

## 步骤 4：先小流量试跑

- 服务端启动后，先用 `limit=3`。
- 客户端勾选“确认真实同步请求”开关。
- 或直接调用：

```bash
curl -X POST http://127.0.0.1:8000/api/xiaohongshu/sync/jobs \
  -H 'Content-Type: application/json' \
  -d '{"limit":3,"confirm_live":true}'
```

## 常见返回与处理

- `AUTH_EXPIRED`：Cookie/签名失效，重新抓请求。
- `RATE_LIMITED`：触发限频，按返回等待秒数后再试。
- `UPSTREAM_ERROR`：路径字段不匹配，检查 `items_path` 与字段名。

## 建议运行节奏

- 单次 3-10 条。
- 每 30 分钟或更久同步一次。
- 避免多设备并发操作同账号。
