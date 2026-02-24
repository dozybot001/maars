# MAARS Backend

## 结构

```
backend/
├── main.py              # FastAPI + Socket.io 入口，注册路由
├── api/                 # 路由、schemas、state（按领域拆分）
│   ├── routes/         # db, plan, plans, execution, monitor, config, workers
│   ├── schemas.py      # Pydantic 请求模型
│   └── state.py        # 共享状态（sio、executor_runner、plan_run_state）
├── planner/             # AI 规划：atomicity → decompose → format
│   ├── index.py         # run_plan 主流程，递归分解
│   ├── llm_client.py    # OpenAI 兼容 LLM 调用（流式+重试）
│   └── prompts/         # LLM prompt 模板
├── monitor/             # 执行阶段
│   ├── from_plan.py     # plan → execution：提取原子任务，依赖继承+下沉+解析
│   ├── timetable.py     # 网格布局（stage 列 + 孤立任务区）
│   └── __init__.py      # build_layout_from_execution 入口
├── layout/              # 图布局
│   ├── graph.py         # build_dependency_graph
│   ├── tree_layout.py   # Planner 分解树：层级布局
│   ├── stage_layout.py  # Monitor 执行树：stage 行
│   └── __init__.py      # compute_decomposition_layout / compute_monitor_layout
├── workers/             # 执行与验证
│   ├── __init__.py      # executor/validator 工作池管理
│   ├── runner.py        # ExecutorRunner：调度执行+验证+状态推送
│   └── execution/       # 具体执行逻辑、artifact 解析
├── tasks/
│   ├── task_stages.py   # 拓扑排序 + 传递规约
│   └── task_cache.py    # build_tree_data（monitor 用）
├── db/                  # 文件存储：db/{plan_id}/plan.json, execution.json, validation.json
├── test/                # Mock AI 响应、mock_stream
└── requirements.txt
```

## 运行

```bash
pip install -r requirements.txt
python3 -m uvicorn main:asgi_app --host 0.0.0.0 --port 3001 --loop asyncio --http h11
```

## 核心数据流

```
plan.json ──Generate Map──→ execution.json ──Execution──→ 状态更新
    ↑                            ↑
 Planner 写入              from_plan.py 生成
```

- **plan.json**：完整任务树（含分解层级和依赖），Planner 视图数据源
- **execution.json**：仅原子任务（依赖已解析，含 stage/status），Monitor 视图数据源
