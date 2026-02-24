# Monitor 模块

执行阶段前置：从 plan 生成 execution，并构建 Monitor 视图布局。

## 职责

- **build_execution_from_plan**：提取原子任务、解析依赖、分 stage
- **build_layout_from_execution**：生成 grid + treeData，供 ExecutorRunner 与前端渲染

## 依赖解析（from_plan.py）

1. **继承**：原子任务继承祖先的跨子树依赖
2. **下沉**：非原子依赖目标替换为其原子后代

## 文件

| 文件 | 用途 |
|------|------|
| from_plan.py | plan → execution：`build_execution_from_plan` |
| timetable.py | 网格布局：`build_task_layout`（stage 列 + 孤立任务区） |
| __init__.py | `build_layout_from_execution` 入口 |

## 相关

- 执行流程详见 [Workers 模块](workers/README.md)
