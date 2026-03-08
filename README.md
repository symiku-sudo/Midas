# Midas

个人多模态知识库助手（MVP）。

## 当前完成状态

- 服务端（FastAPI）：已完成
  - `GET /health`
  - `GET /api/finance/signals`
  - `POST /api/bilibili/summarize`（`video_url` 支持完整链接或直接传 `BV` 号）
  - `POST /api/xiaohongshu/summarize-url`
  - `POST /api/xiaohongshu/auth/update`
  - `POST /api/notes/merge/suggest|preview|commit|rollback|finalize`
- Android 客户端（Compose）：已完成最小可用版本
  - 服务端地址配置与持久化
  - 连接测试
  - B 站总结请求与 Markdown 展示
  - 小红书按 URL 单篇总结与结果展示
  - 资产系统面板（资产统计 + Watchlist Preview + RSS Insight）
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
- Android 端左上角可切换“笔记系统 / 资产系统”；资产系统分为两屏：`Watchlist+RSS` 与 `资产统计`。
- `Watchlist+RSS` 面板会在资产系统打开时自动轮询刷新；若 RSS 拉取超过阈值未更新，会显示“数据可能陈旧”提示。
- Watchlist 行会显式展示监控阈值标签；RSS 命中会按来源权重排序，并对同主题标题去重。
- `资产统计` 采用“万元人民币”单位，按风险从高到低展示分类（股票、股票基金、黄金、债券/债券基金、货币基金、银行定期存款、银行活期存款、公积金）。
- 支持一键复制资产概况文本（可直接粘贴给大模型咨询资产配置问题）。
- 每次保存都会本地记录一条资产快照（含时间戳、总资产、各分类金额）；前端提供历史列表（近到远）、详情查看与单条删除（删除会同步持久化）。
- B站/小红书新生成摘要会额外附带“评论区洞察（含点赞权重）”章节（best-effort）。
- 每次新增已保存笔记（B站/小红书）后，服务端会自动备份一次数据库（位于 `server/.tmp/backups/`）。
- Android 端可通过内置 WebView 登录并上传 Cookie/UA 到服务端（`/api/xiaohongshu/auth/update`），减少手工 HAR/cURL 更新频率。
- 当前默认 `llm.enabled=true`、`asr.mode=faster_whisper`、`asr.model_size=base`。
- 智能合并候选可启用本地 embedding 语义相似（`server/config.yaml` 的 `notes_merge.*`）。
- merged 笔记正文末尾会自动追加“原始笔记来源”（原始标题 + 可点击链接）。
- 笔记库接口返回的 `saved_at` 统一按东八区（UTC+08:00）显示。
- 真实小红书网页端接口回放仍有平台风控风险，建议低频、小批量执行。
