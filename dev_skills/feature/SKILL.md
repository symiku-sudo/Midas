---
name: feature
description: 在 Midas 中实现新功能或增强能力。适用于新增接口、扩展服务流程、增加配置项、补充客户端/服务端能力。
---

# Feature（功能开发）

## 必须流程
1. 复述目标与 DoD。
2. 给出计划：改哪些文件、如何验证、风险点。
3. 小步实现，优先复用现有模块。
4. 为核心逻辑补测试（接口级或服务级至少一个）。
5. 运行验证并记录结果。
6. 同步文档后提交。

## Midas 约束
- 不破坏既有 API 协议与错误码语义。
- 新增配置项必须写入 `config.example.yaml` 与 `config.yaml`。
- 若新增接口或响应字段，必须更新：
  - `server/API_CONTRACT.md`
  - `server/README.md`
- 周进度文档必须更新：`WEEKLY_PROGRESS.md`。

## 最低交付
- 代码改动
- 对应测试
- 文档更新
- commit 信息
