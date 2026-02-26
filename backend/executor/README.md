# Executor

任务执行与调度。Generate Map 后，`ExecutorRunner` 调度 executor 池执行任务、validator 池验证输出。

## 流程

```
POST /monitor/timetable → set_layout
POST /execution/run → start_execution
```

## 文件

| 文件 | 用途 |
|------|------|
| runner.py | ExecutorRunner：调度、状态持久化、WebSocket 推送 |
| [execution/](execution/) | LLM 执行、artifact 解析、Agent 工具 |
| __init__.py | executor_manager（7 个 worker） |
