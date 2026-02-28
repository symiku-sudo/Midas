# Midas Android Client

## 功能

- 服务端地址设置（持久化）
- 可编辑服务端运行配置：精简常用项、中文说明、布尔开关/下拉/文本输入与一键恢复默认
- 连接测试（`/health`）
- B 站总结（`/api/bilibili/summarize`）
- B 站总结保存到笔记库（`/api/notes/bilibili/save`）
- 小红书单篇 URL 总结（`/api/xiaohongshu/summarize-url`）
- 小红书单篇总结保存到笔记库（`/api/notes/xiaohongshu/save-batch`，按单篇触发）
- 笔记库阅读/检索、单条删除与分组清空（B站/小红书独立）
- 小红书 auth 刷新（用于单篇总结前准备登录态）
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

导出 APK：

```bash
tools/export_apk.sh
```

常用参数：

```bash
# 导出 release（若未配置正式签名，会自动用本地 debug keystore 生成可安装包）
tools/export_apk.sh --release

# 指定导出目录和文件名
tools/export_apk.sh --output /mnt/d/Exports --name midas-debug.apk
```

脚本默认把 WSL 构建缓存写入独立目录（`.gradle-wsl/`、`.build-wsl/`、`.kotlin-wsl/`），避免与 Windows/Android Studio 的缓存互相污染。

如果你已经遇到过 `different roots` 这类路径混用报错，先在 `android/` 下执行一次清理再重编译：

```bash
rm -rf .gradle app/build build .kotlin
```

> 说明：客户端默认地址 `http://10.0.2.2:8000/`（Android 模拟器访问宿主机）。

## 结构

- `app/src/main/java/com/midas/client/data/`：数据模型、网络层、仓储
- `app/src/main/java/com/midas/client/ui/`：Compose 页面与主题
- `app/src/main/java/com/midas/client/MainActivity.kt`：入口
