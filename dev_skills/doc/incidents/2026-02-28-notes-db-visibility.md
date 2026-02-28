# 2026-02-28 事故复盘：笔记库“看起来被清空”

## 1. 背景与影响
- 用户反馈：Android 端“刷新笔记库”后看不到历史笔记，误判为“数据库被清空”。
- 影响范围：小红书/笔记库可见性异常，授权与同步链路也出现连带困惑（`AUTH_EXPIRED`、上游解析异常）。

## 2. 时间线（绝对时间）
1. 2026-02-26：提交 `7281460`，`dev_server.sh` 在 WSL 下默认改为 detached 启动。
2. 2026-02-28：执行 release 流程（`tools/release.sh`），其中包含 `server/tools/dev_server.sh restart web_guard --mobile`。
3. 2026-02-28：用户反馈“刷新笔记后为空”，并质疑数据库被清空。

## 3. 根因链路
1. `xiaohongshu.db_path` 使用相对路径：`.tmp/midas.db`。
2. 仓库层直接 `Path(db_path).expanduser()`，未锚定到固定基准目录。
3. WSL detached 启动流程在子进程里先 `cd $SERVER_DIR`，改变了进程 cwd。
4. 相对路径在不同 cwd 下会指向不同物理文件，导致“读取到另一份数据库”或“新建空库”，外在表现等同“库空了”。

## 4. 证据
- 进程工作目录：
  - `/proc/<pid>/cwd -> /mnt/d/MyWork/midas/server`
- 同名数据库文件同时存在：
  - `/mnt/d/MyWork/midas/server/.tmp/midas.db`（2026-02-28 03:43，36KB）
  - `/mnt/d/MyWork/midas/.tmp/midas.db`（2026-02-26 00:46，20KB）
- 关键提交证据：
  - `7281460 chore(server): default dev server start to detached mode in WSL`
  - 变更包含 `cd $SERVER_DIR` 后再启动 `run_local_stack.sh` 的路径。
- 证据缺口：
  - `local_server.log` 会被重启覆盖，无法回看更早时段是否触发过 `DELETE /api/notes/xiaohongshu`。

## 5. 处置与回滚
1. 本次先完成复盘沉淀与 skill 约束升级，避免再次“定位到了但没流程化”。
2. 运行时排查时必须同步检查：
   - 当前 `config.yaml` 的 `xiaohongshu.db_path`
   - 进程 cwd
   - 实际使用的绝对数据库路径与表计数

## 6. 防再发动作
1. 代码动作：将 `db_path` 在加载配置后统一解析为绝对路径（锚定 `config.yaml` 所在目录），禁止依赖 cwd。
2. 代码动作：服务启动日志打印“实际数据库绝对路径 + 三张表计数”。
3. 产品动作：对“清空笔记”接口增加强确认（双确认或确认字段）。
4. 脚本动作：release 前做数据库快照（按时间戳复制 `.db`）。
5. 文档动作：后续同类事件必须新增 `dev_skills/doc/incidents/YYYY-MM-DD-*.md`。
