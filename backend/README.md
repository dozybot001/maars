# MAARS Backend

## 结构

```
backend/
├── main.py              # FastAPI + Socket.io 入口
├── planner/             # AI 规划（verify/decompose/format）
├── monitor/             # 布局、execution 生成
├── workers/             # executor、verifier、runner
├── tasks/               # 任务缓存与阶段计算
├── db/                  # db/{plan_id}/plan.json, execution.json, verification.json
├── test/                # mock-ai、mock_stream
└── docs/
```

## 运行

```bash
pip install -r requirements.txt
python3 -m uvicorn main:asgi_app --host 0.0.0.0 --port 3001 --loop asyncio --http h11
```
