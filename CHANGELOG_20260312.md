# Changelog - 2026-03-12

记录 2026-03-12 当天在 Midas 上完成的主要功能、接口、客户端接入、测试与文档同步。

## 基线

- 打了基线 tag：`pre-roadmap-20260312-1220`

## 异步任务中心

- 服务端新增异步任务能力：提交、列表、详情、失败/中断重试。
- 新增接口：
  - `POST /api/jobs/bilibili-summarize`
  - `POST /api/jobs/xiaohongshu/summarize-url`
  - `GET /api/jobs`
  - `GET /api/jobs/{job_id}`
  - `POST /api/jobs/{job_id}/retry`
- 任务历史持久化到 `server/.tmp/async_jobs.json`
- Android 接入异步任务：
  - B站/小红书总结改为后台任务
  - 面板可看最近任务
  - 可回看成功结果
  - 可重试失败/中断任务

关键文件：

- [server/app/services/async_jobs.py](/mnt/d/MyWork/midas/server/app/services/async_jobs.py)
- [server/app/api/routes.py](/mnt/d/MyWork/midas/server/app/api/routes.py)
- [server/app/models/schemas.py](/mnt/d/MyWork/midas/server/app/models/schemas.py)
- [android/app/src/main/java/com/midas/client/ui/screen/MainViewModel.kt](/mnt/d/MyWork/midas/android/app/src/main/java/com/midas/client/ui/screen/MainViewModel.kt)
- [android/app/src/main/java/com/midas/client/ui/screen/MainScreen.kt](/mnt/d/MyWork/midas/android/app/src/main/java/com/midas/client/ui/screen/MainScreen.kt)

## 笔记库

- 服务端新增统一笔记搜索：`GET /api/notes/search`
- Android 笔记库改成远端搜索
- B站/小红书笔记支持分组清空

关键文件：

- [server/app/repositories/note_repo.py](/mnt/d/MyWork/midas/server/app/repositories/note_repo.py)
- [server/app/services/note_library.py](/mnt/d/MyWork/midas/server/app/services/note_library.py)
- [server/app/api/routes.py](/mnt/d/MyWork/midas/server/app/api/routes.py)

## 轻量鉴权

- 服务端新增可选 `auth.access_token`
- Android 设置页支持保存 token，并自动透传 `Authorization: Bearer ...`

关键文件：

- [server/app/core/config.py](/mnt/d/MyWork/midas/server/app/core/config.py)
- [server/app/middleware/access_token.py](/mnt/d/MyWork/midas/server/app/middleware/access_token.py)
- [android/app/src/main/java/com/midas/client/data/network/MidasApiFactory.kt](/mnt/d/MyWork/midas/android/app/src/main/java/com/midas/client/data/network/MidasApiFactory.kt)
- [android/app/src/main/java/com/midas/client/data/repo/SettingsRepository.kt](/mnt/d/MyWork/midas/android/app/src/main/java/com/midas/client/data/repo/SettingsRepository.kt)

## Finance Signals：联动

- 服务端把 Top5 新闻和 watchlist 做了关联归并
- 新字段：
  - `watchlist_preview[].related_news_count`
  - `watchlist_preview[].related_keywords`
  - `top_news[].related_symbols`
  - `top_news[].related_watchlist_names`
- Android 展示：
  - Watchlist 行显示“关联新闻数/关键词”
  - 新闻卡显示“影响哪些关注项”

关键文件：

- [server/app/services/finance_signals.py](/mnt/d/MyWork/midas/server/app/services/finance_signals.py)
- [server/finance_signals/financial_config.yaml](/mnt/d/MyWork/midas/server/finance_signals/financial_config.yaml)
- [android/app/src/main/java/com/midas/client/data/model/ApiModels.kt](/mnt/d/MyWork/midas/android/app/src/main/java/com/midas/client/data/model/ApiModels.kt)
- [android/app/src/main/java/com/midas/client/ui/screen/MainScreen.kt](/mnt/d/MyWork/midas/android/app/src/main/java/com/midas/client/ui/screen/MainScreen.kt)

## Finance Signals：建议卡

- 服务端新增 `focus_cards`
- 第一版把两类信号整理成“今日关注建议”：
  - 阈值已触发的标的
  - 明确影响 watchlist 的新闻
- Android 在 `Watchlist+新闻` 面板顶部展示建议卡

关键文件：

- [server/app/models/schemas.py](/mnt/d/MyWork/midas/server/app/models/schemas.py)
- [server/app/services/finance_signals.py](/mnt/d/MyWork/midas/server/app/services/finance_signals.py)
- [android/app/src/main/java/com/midas/client/ui/screen/MainScreen.kt](/mnt/d/MyWork/midas/android/app/src/main/java/com/midas/client/ui/screen/MainScreen.kt)

## Finance Signals：动作语义

- 建议卡新增动作字段：
  - `action_label`
  - `action_hint`
  - `action_type`
  - `reasons`
- Android 已展示：
  - 动作标签
  - 动作提示
  - 触发原因
- 这让后续按动作类型筛选/排序变得可做

关键文件：

- [server/app/models/schemas.py](/mnt/d/MyWork/midas/server/app/models/schemas.py)
- [server/app/services/finance_signals.py](/mnt/d/MyWork/midas/server/app/services/finance_signals.py)
- [android/app/src/main/java/com/midas/client/data/model/ApiModels.kt](/mnt/d/MyWork/midas/android/app/src/main/java/com/midas/client/data/model/ApiModels.kt)
- [android/app/src/main/java/com/midas/client/ui/screen/MainScreen.kt](/mnt/d/MyWork/midas/android/app/src/main/java/com/midas/client/ui/screen/MainScreen.kt)

## 测试

服务端补强：

- [server/tests/test_async_jobs_service.py](/mnt/d/MyWork/midas/server/tests/test_async_jobs_service.py)
- [server/tests/test_api.py](/mnt/d/MyWork/midas/server/tests/test_api.py)
- [server/tests/test_note_repo.py](/mnt/d/MyWork/midas/server/tests/test_note_repo.py)
- [server/tests/test_finance_signals_service.py](/mnt/d/MyWork/midas/server/tests/test_finance_signals_service.py)

Android 补强：

- [android/app/src/test/java/com/midas/client/ui/screen/MainScreenContentRobolectricSmokeTest.kt](/mnt/d/MyWork/midas/android/app/src/test/java/com/midas/client/ui/screen/MainScreenContentRobolectricSmokeTest.kt)

## 文档

已同步：

- [README.md](/mnt/d/MyWork/midas/README.md)
- [server/README.md](/mnt/d/MyWork/midas/server/README.md)
- [server/API_CONTRACT.md](/mnt/d/MyWork/midas/server/API_CONTRACT.md)
- [android/README.md](/mnt/d/MyWork/midas/android/README.md)

## 结果

- 服务端当前关键回归：`46 passed`
- Android 当前单测：`BUILD SUCCESSFUL`
