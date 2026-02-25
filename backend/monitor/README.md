# Monitor 模块

从 plan 生成 execution，构建 Monitor 视图布局。执行流程见 [Workers](workers/README.md)。

- **build_execution_from_plan**：提取原子任务、解析依赖（继承+下沉）、分 stage
- **build_layout_from_execution**：生成 grid + treeData

## 文件

| 文件 | 用途 |
|------|------|
| from_plan.py | plan → execution：`build_execution_from_plan` |
| timetable.py | 网格布局：`build_task_layout`（stage 列 + 孤立任务区） |
| __init__.py | `build_layout_from_execution` 入口 |
