# Changelog 2026-03-15

## Android

- 新增首页总览，启动后先展示最近任务、最近新增笔记、今日财经建议和高频入口。
- 笔记页补充来源/时间/已合并/排序筛选，并新增主题回顾、时间回顾、相似笔记回查。
- 财经建议改为服务端状态闭环，支持已看过、今日忽略、保持关注与恢复活跃。

## Server

- 新增 `GET /api/home/overview` 聚合首页总览数据。
- Finance Signals 新增建议卡状态更新与建议历史接口，并把资产暴露关联进 watchlist / news / focus cards。
- 笔记库检索新增时间、已合并、排序筛选；新增主题回顾、时间回顾和相关笔记回查接口。
- 清理 `XiaohongshuSyncService` 兼容命名，统一使用 `XiaohongshuService`。

## Engineering

- 固化 release / smoke / APK 分发流程，APK 导出脚本现在会输出候选产物、时间戳和 SHA256。
- 新增 `tools/SMOKE_CHECKLIST.md` 作为统一冒烟清单。
