# MAARS Backend

## 目录结构（按区域分类）

```
backend/
├── main.py              # FastAPI + Socket.io 入口
├── requirements.txt
├── db/                  # 数据存储
│   └── {plan_id}/       # plan.json, execution.json, idea.json
├── monitor/             # Monitor 区域：布局、execution 生成
│   ├── __init__.py      # build_layout_from_execution, build_execution_from_plan
│   ├── timetable.py     # 时间表布局
│   └── from_plan.py     # 从 plan 生成 execution
├── planner/             # Planner 区域：AI 规划
│   ├── __init__.py
│   ├── index.py
│   └── prompts/
├── workers/             # Worker 区域：executor、verifier 工作池
│   ├── __init__.py      # executor_manager, verifier_manager, ExecutorRunner
│   └── runner.py        # 任务执行与验证
├── tasks/               # 任务阶段与缓存
│   ├── task_cache.py
│   └── task_stages.py
├── test/                # 测试：mock AI、mock data
│   ├── mock-ai/         # verify.json, decompose.json, format.json
│   └── mock_stream.py
├── docs/
└── README.md
```

## 运行

```bash
cd backend
python3 -m uvicorn main:asgi_app --host 0.0.0.0 --port 3001 --loop asyncio --http h11
```
