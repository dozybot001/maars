# API

FastAPI 路由与请求模型。

## 结构

- **routes/**：按领域拆分（db, plan, plans, execution, config, executors, validation）
- **schemas.py**：Pydantic 请求模型
- **state.py**：共享状态（sio、executor_runner、plan_run_state）
