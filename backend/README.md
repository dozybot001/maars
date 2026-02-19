# MAARS Backend

## 结构

```
backend/
├── main.py              # FastAPI + Socket.io 入口
├── planner/             # AI 规划（atomicity/decompose/format）
├── monitor/             # 布局、execution 生成
├── workers/             # executor、validator (output validation)、runner
├── tasks/               # 任务缓存与阶段计算
├── db/                  # db/{plan_id}/plan.json, execution.json, validation.json
├── test/                # mock-ai、mock_stream
└── requirements.txt
```

## 运行

```bash
cd backend
pip install -r requirements.txt
python3 -m uvicorn main:asgi_app --host 0.0.0.0 --port 3001 --loop asyncio --http h11
```

访问 http://localhost:3001
