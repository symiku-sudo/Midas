# Externalized ntfy Toolkit

`ntfy` 通知系统已迁移为 `midas` 子模块：

- 默认路径：`tools/ntfy-notify`

`midas` 内保留了两个代理脚本：

- `tools/ntfy_notify.sh`
- `tools/ntfy_selfhost.sh`

这两个脚本会转发到子模块同名脚本；如路径不同，可设置：

```bash
export NTFY_NOTIFY_REPO_DIR=/abs/path/to/ntfy-notify
```

如果本地还没初始化子模块，请先执行：

```bash
git submodule update --init --recursive
```

完整说明请查看 `tools/ntfy-notify/README.md`（包含自建、鉴权、跨项目通知格式示例）。
