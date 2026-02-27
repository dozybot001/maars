# Planner Visualization

Planner 可视化区域：Decomposition Tree、Execution Graph。

## 职责

- **build_execution_from_plan**：提取原子任务、解析依赖（继承+下沉）、分 stage
- **build_layout_from_execution**：生成 treeData + layout（供 execution graph）

## 子视图

| 子视图 | 模块 | 用途 |
|--------|------|------|
| Decomposition Tree | planner.layout | 分解树布局（按 task_id 层级 level-order） |
| Execution Graph | layout/ | 执行图 stage 布局 |

## 文件

| 文件 | 用途 |
|------|------|
| from_plan.py | plan → execution |
| timetable.py | treeData 构建（供 execution graph） |
| [layout/](layout/) | Execution Graph 布局 |
| [tasks/](tasks/) | 拓扑排序、传递规约 |
