---
name: run_main
description: Midas 运行闭环技能。用于在本地持续执行“测试/启动/接口验证 -> 修复 -> 重跑”直到通过。
---

# Run Main（运行闭环）

## 目标
在同一轮任务中，持续修复并重跑，直到达到可交付状态。

## 标准流程
1. 进入服务端目录并激活环境。
2. 执行测试：`python -m pytest -q`。
3. 若测试失败，定位并修复后重跑。
4. 若测试通过，启动服务并做基础接口检查（至少 `/health`）。
5. 若接口失败，修复并回到步骤 2。

## 推荐命令
```bash
cd server
source .venv/bin/activate
python -m pytest -q
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## 终止条件
- 测试通过。
- 基础接口可用（至少 `/health` 成功）。
- 不存在明显阻断错误。

## 输出要求
- 本轮执行命令
- 失败签名（如有）
- 修复摘要
- 最终验证结果
