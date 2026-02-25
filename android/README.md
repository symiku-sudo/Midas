# Midas Android Client

## 功能

- 服务端地址设置（持久化）
- 可编辑服务端运行配置（排除敏感字段）：逐字段表单编辑（布尔开关 + 文本输入）与一键恢复默认
- 连接测试（`/health`）
- B 站总结（`/api/bilibili/summarize`）
- B 站总结保存到笔记库（`/api/notes/bilibili/save`）
- 小红书同步进度（`/api/xiaohongshu/sync/jobs` + 轮询状态）
- 小红书总结批量保存到笔记库（`/api/notes/xiaohongshu/save-batch`）
- 笔记库阅读/检索、单条删除与分组清空（B站/小红书独立）
- 小红书真实同步确认开关（对应 `confirm_live`）
- 错误码场景化提示（`AUTH_EXPIRED` / `RATE_LIMITED` / `CIRCUIT_OPEN` 等）
- Markdown 渲染展示（Markwon）

## 构建

1. 用 Android Studio 打开 `android/`。
2. 同步 Gradle。
3. 运行 `app` 模块。

若需在 WSL 终端由 agent 直接编译：

```bash
cd android
tools/wsl_android_build.sh
```

也可传自定义任务：

```bash
tools/wsl_android_build.sh :app:assembleDebug :app:testDebugUnitTest
```

> 说明：客户端默认地址 `http://10.0.2.2:8000/`（Android 模拟器访问宿主机）。

## 结构

- `app/src/main/java/com/midas/client/data/`：数据模型、网络层、仓储
- `app/src/main/java/com/midas/client/ui/`：Compose 页面与主题
- `app/src/main/java/com/midas/client/MainActivity.kt`：入口
