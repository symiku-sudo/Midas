---
name: cache-sync
description: Midas 开发缓存清理与同步规范。用于清理测试缓存、临时数据库和可复现样本，保障本地复现实验一致性。
---

# Cache Sync（缓存同步与清理）

## 适用场景
- 本地状态污染导致测试不稳定。
- 需要复现实验前的“干净环境”。
- 需要清理临时 SQLite 与 pytest 缓存。

## 推荐流程
1. 清理测试缓存与临时产物。
2. 确认不会误删源码或文档。
3. 重跑测试验证环境恢复。

## 推荐命令
```bash
cd server
rm -rf .pytest_cache
rm -rf .tmp
python -m pytest -q
```

## 约束
- 禁止删除源码、配置模板和文档。
- 禁止提交本地运行缓存（如 `.tmp/`、`.pytest_cache/`、临时日志）。
- 清理动作必须可复现、可审计。
