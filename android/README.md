# Midas Android Client

## 功能

- 服务端地址设置（持久化）
- 连接测试（`/health`）
- B 站总结（`/api/bilibili/summarize`）
- 小红书同步进度（`/api/xiaohongshu/sync/jobs` + 轮询状态）
- Markdown 渲染展示（Markwon）

## 构建

1. 用 Android Studio 打开 `android/`。
2. 同步 Gradle。
3. 运行 `app` 模块。

> 说明：客户端默认地址 `http://10.0.2.2:8000/`（Android 模拟器访问宿主机）。

## 结构

- `app/src/main/java/com/midas/client/data/`：数据模型、网络层、仓储
- `app/src/main/java/com/midas/client/ui/`：Compose 页面与主题
- `app/src/main/java/com/midas/client/MainActivity.kt`：入口
