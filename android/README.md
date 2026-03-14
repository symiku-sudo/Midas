# Midas Android Client

## 功能

- 单层导航：`B站 / 小红书 / 笔记 / 资产 / 设置`
- 资产系统内提供 `市场信号 / 资产总览` 双页签
- `Watchlist+RSS` 面板会显示新闻与关注标的的联动关系：新闻卡可见“影响哪些关注项”，Watchlist 行可见“关联新闻数/关键词”
- `Watchlist+RSS` 面板会额外显示“今日关注建议”，优先呈现阈值触发和明确影响 watchlist 的新闻，并附上建议动作
- 建议卡会按 `action_type` 分组展示，并支持端侧“已处理 / 恢复全部”
- 建议卡内部已接入结构化 `action_type/reasons`，当前用于更稳定地展示“立即处理 / 继续跟进 / 持续观察”和触发原因
- Top5 新闻默认先展示 3 条，按需再展开全部，避免首屏信息过满
- 资产统计支持“万元人民币”录入、按风险从高到低排序展示、一键复制资产概况
- 资产统计支持“图片识别回填”：最多上传 5 张图片，端侧压缩后上传服务端识别并回填（不自动保存）
- 资产统计的“当前金额”和“历史快照”均改为服务端持久化；客户端会在首次连上服务端时自动迁移旧版本遗留的本地数据
- 服务端地址设置（持久化）
- 可选访问令牌设置（持久化；启用服务端 `auth.access_token` 时自动透传 `Authorization: Bearer <token>`）
- 可编辑服务端运行配置：精简常用项、中文说明、布尔开关/下拉/文本输入与一键恢复默认
- 连接测试（`/health`）
- B 站总结（客户端走异步任务接口，后台轮询完成后展示结果）
- B 站最近任务卡片：支持刷新历史、查看已完成结果、重试失败/中断任务
- B 站总结保存到笔记库（`/api/notes/bilibili/save`）
- 小红书单篇 URL 总结（客户端走异步任务接口，后台轮询完成后展示结果）
- 小红书批量同步：可查看待同步数量、冷却状态、提交异步批量任务、边跑边看进度
- 小红书最近任务卡片：支持刷新历史、查看已完成结果、重试失败/中断任务；覆盖单篇总结和批量同步两类任务
- 小红书结果支持“保存单篇 / 保存当前全部结果”
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
> 若服务端启用了 `auth.access_token`，请在客户端设置页一并填写访问令牌。

## ntfy（Tailscale 内网通知）

如果你已按仓库根目录的 `tools/ntfy_selfhost.sh` 部署好自建 ntfy，Android 端建议按下面配置：

1. 打开 Tailscale 并保持加入同一 tailnet。
2. 安装 ntfy App（优先 F-Droid 版本）。
3. 在 ntfy App 添加服务器：`http://<tailnet-host-or-ip>:8085`。
4. 订阅你的 topic（例如 `midas-task`）。
5. 若服务端启用鉴权，配置账号或 Bearer Token。
6. 关闭 `Tailscale` 与 `ntfy` 的电池优化（允许后台运行）。

发送端可直接用：

```bash
tools/ntfy_notify.sh --config .tmp/ntfy/notify.env
```

## 结构

- `app/src/main/java/com/midas/client/data/`：数据模型、网络层、仓储
- `app/src/main/java/com/midas/client/ui/`：Compose 页面与主题
- `app/src/main/java/com/midas/client/MainActivity.kt`：入口
