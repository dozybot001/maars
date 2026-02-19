# 任务树与 Timetable 渲染逻辑说明

本文档描述 MAARS 后端中任务树（Task Tree）与 Timetable（时间表/网格）的数据处理与渲染流程。

---

## 一、目录结构

```
backend/
├── main.py                # 主入口，FastAPI + Socket.io
├── tasks/                 # 任务处理模块
│   ├── task_cache.py     # 缓存提取、stage 计算、treeData 构建
│   └── task_stages.py    # 拓扑排序、依赖清洗、stage 注入（networkx）
├── monitor/               # Monitor 模块
│   ├── __init__.py       # build_layout_from_execution
│   └── timetable.py      # build_task_layout、clean_dependencies
├── planner/               # Planner 模块（AI 规划）
├── workers/               # Executor、Validator 模块
├── db/                    # 数据持久化
└── test/                 # Mock AI、mock_stream
```

---

## 二、核心概念

### 2.1 treeData 格式

统一使用 **flat 格式**，每个任务为独立对象：

```json
{
  "task_id": "1",
  "description": "文献调研：...",
  "dependencies": ["0"],
  "stage": 2
}
```

- `stage`：1-based，由后端计算
- 展示时直接使用 `task_id` 和 `description`（或 `objective`）

### 2.2 任务命名规范

- **task_id 格式**：0（idea）；1, 2, 3, 4（0 的子任务）；1_1, 1_2（1 的子任务）；1_1_1, 1_1_2（1_1 的子任务）。纯数字层级。

**Atomic 任务**：经「分解→验证→格式化」流程后，atomic 任务会带有 `input`、`output` 字段，供 Executor 明确消耗与产出。

**依赖下沉 (sinkDependencies)**：Plan 是动态的、不断向下延伸的。当父任务被分解后，指向它的依赖应下沉到其子任务叶子，父任务不再出现在依赖线中。例如 4 依赖 1，且 1 有子任务（1_1, 1_2, ...），则 4 的依赖下沉为 1 的叶子任务（如 1_5）。适用于任意层级，由 `taskStages.sinkDependencies` 自动完成。

### 2.3 staged 格式

用于内部处理，按 stage 分组的二维数组：

```javascript
[
  [{ task_id: "0", ... }],                               // stage 1
  [{ task_id: "1", ... }, { task_id: "2", ... }],         // stage 2
  ...
]
```

---

## 三、任务树（Task Tree）流程

### 3.1 数据来源

| 场景 | 数据来源 | 触发方式 |
|------|----------|----------|
| Planner 任务树 | `plan.tasks`（db/plan.json） | `GET /api/plan/tree`、socket `plan-complete` |
| Monitor 任务树 | `execution.tasks`（db/execution.json） | `timetableLayout.treeData`（来自 Monitor 布局） |

### 3.2 后端处理：`tasks/buildTreeData`

```
tasks (完整数据，来自 db)
    │
    ▼
extractCacheFromTasks(tasks)
    → cache: [{ task_id, dependencies }]
    │
    ▼
computeStaged(cache)  →  tasks/taskStages.computeTaskStages
    ├─ sinkDependencies（依赖下沉：父任务已分解时，依赖转移到其子任务叶子）
    ├─ 拓扑排序（按依赖关系分层）
    ├─ cleanDependencies（只保留前一 stage 的依赖）
    └─ 注入 stage (1-based)
    │
    ▼
enrichTreeData(staged, tasks)
    → 按 task_id 用 tasks 的完整数据合并到 staged 结果
    │
    ▼
treeData (flat，含 stage、description 等；Plan 不含 status，Execution 含 status)
```

**相关文件：**

- `tasks/task_cache.py`：`build_tree_data`、`extract_cache_from_tasks`、`enrich_tree_data`
- `tasks/task_stages.py`：`compute_task_stages`
- `monitor/timetable.py`：`clean_dependencies`

### 3.3 前端渲染

- **入口**：`TaskTree.renderPlannerTree(treeData)` / `TaskTree.renderMonitorTasksTree(treeData)`
- **逻辑**：使用 dagre 布局 → 绘制节点与连线
- **差异**：Planner 不显示 status，Monitor 显示 status 样式

---

## 四、Timetable（时间表）流程

### 4.1 数据来源

- 请求体中的 `execution`（或从 db 加载）
- API：`POST /api/monitor/timetable`

### 4.2 后端处理：`monitor/buildLayoutFromExecution`

```
execution.tasks (fullTasks)
    │
    ▼
tasks/buildTreeData(fullTasks)
    → treeData (flat)
    │
    ▼
groupByStage(treeData)
    → staged [[stage0], [stage1], ...]
    │
    ▼
monitor/timetable.buildTaskLayout(staged)
    │
    ├─ 分类：dependencyTasks / isolatedTasks
    ├─ 依赖任务：按列布局，列内按「最右依赖」分组排布
    ├─ 生成 grid[row][col]、isolatedTasks
    └─ 直接使用 task 原始数据（task_id、description）
    │
    ▼
{ grid, treeData, isolatedTasks, maxRows, maxCols }
```

### 4.3 buildTaskLayout 详细逻辑

1. **任务分类**
   - 有依赖或被依赖 → `dependencyTasks`
   - 无依赖且无被依赖 → `isolatedTasks`

2. **依赖任务列布局**
   - 第 0 列：无依赖任务
   - 后续列：依赖已放置任务
   - 每列内按「最右依赖」分组，同组任务垂直排列

3. **输出**
   - `grid`：`grid[row][col]` 为 task 或 null
   - `isolatedTasks`：独立任务列表
   - `treeData`：flat 列表（含 display 信息）

### 4.4 前端渲染

- **左侧网格**：遍历 `grid`，生成 `.timetable-cell`
- **右侧区域**：渲染 `isolatedTasks`
- **Monitor 任务树**：`TaskTree.renderMonitorTasksTree(timetableLayout.treeData)`

---

## 五、依赖关系图

```
                    ┌─────────────────────────────────────────────────────────┐
                    │                    Planner 任务树                        │
                    │  plan.json → buildTreeData → treeData → renderPlannerTree │
                    │  (或 socket plan-complete 直接带 treeData)                 │
                    └─────────────────────────────────────────────────────────┘

                    ┌─────────────────────────────────────────────────────────┐
                    │                   Monitor 任务树 + Timetable             │
                    │  execution.json → buildTreeData → treeData               │
                    │       → groupByStage → buildTaskLayout                   │
                    │       → { grid, treeData, isolatedTasks }                │
                    │       → renderNodeDiagramFromCache (grid + isolated)     │
                    │       → renderMonitorTasksTree(treeData)                 │
                    └─────────────────────────────────────────────────────────┘
```

---

## 六、模块依赖

```
main.py
  ├── tasks.task_cache
  ├── monitor
  │     ├── tasks.task_cache
  │     └── monitor.timetable
  └── ...

tasks.task_cache
  └── tasks.task_stages

tasks.task_stages
  └── monitor.timetable (clean_dependencies)
```

---

## 七、API 一览

| API | 说明 |
|-----|------|
| `GET /api/plan/tree` | 返回 `{ treeData }`，用于 Planner 任务树 |
| `POST /api/monitor/timetable` | 接收 `{ execution }`，返回 `{ layout }`，含 `grid`、`treeData`、`isolatedTasks` |
