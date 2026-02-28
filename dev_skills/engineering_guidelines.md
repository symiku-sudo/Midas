# Midas 开发技能与工程规范

## 1. 项目上下文
- 项目身份：Midas 是个人多模态知识库助手，采用 Client-Server 架构。
- 当前阶段重点：先完成服务端 MVP，再推进 Android 客户端联调。
- 服务端目录：`server/`。
- 关键能力：
  - B 站总结链路（音频下载 -> ASR -> LLM）。
  - 小红书同步链路（限量、去重、随机延迟、熔断）。

## 2. 架构与边界
- API 层：`server/app/api/`
- 核心能力层：`server/app/services/`
- 数据访问层：`server/app/repositories/`
- 配置与错误协议：`server/app/core/`
- 数据模型：`server/app/models/`
- 测试：`server/tests/`

必须保持：
1. 统一响应格式：`ok/code/message/data/request_id`。
2. 所有业务错误映射到明确错误码，不透传原始 traceback 给客户端。
3. 配置驱动：可调整参数放到 `config.yaml`，禁止硬编码可调项。

## 3. 编码原则
- 小步修改，避免一次性大重写。
- 公共函数和核心类保持类型标注。
- 优先复用现有服务和模型，不重复造轮子。
- 仅在必要时新增依赖；新增依赖必须更新 `requirements.txt`。
- 禁止把敏感信息（Cookie、API Key）写入日志。

## 4. 测试与验收
- 任何功能改动至少补一个对应测试（接口或服务级别）。
- 交付前运行：
  - `cd server && source .venv/bin/activate && python -m pytest -q`
- 关键验收项：
  - 接口可用。
  - 错误码可区分。
  - 文档已同步（`README.md`、`API_CONTRACT.md`）。

## 5. 文档与交接
- 行为变化必须同步更新文档。
- 每个阶段完成后在相关文档中补充阶段结论，至少包含：
  - 已完成
  - 未完成
  - 下次接续建议

## 6. 安全与运行约束
- 不读取或输出 `.env` 实际密钥内容。
- 小红书 Cookie 仅允许服务端本地配置与使用。
- 路径处理优先 `pathlib`。涉及“有状态文件”（如 `.db`）时，必须在启动时解析为稳定绝对路径（基于配置文件目录），避免因进程 cwd 变化导致读到另一份数据。

## 7. 事故复盘沉淀
- 发生数据风险事件后，必须在 `dev_skills/doc/incidents/` 新增复盘文档。
- 复盘文档需可操作，至少包含：触发条件、可复现实验、证据、修复动作、防再发动作。
