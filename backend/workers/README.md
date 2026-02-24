# Workers 模块 — 执行阶段工作流

执行阶段包含 **Generate Map**（生成执行图）与 **Execution**（任务执行与验证）。

---

## 一、整体流程

```
Plan (plan.json)
  → Generate Map: build_execution_from_plan → execution.json
  → POST /monitor/timetable → ExecutorRunner.set_layout (chain_cache + plan_id)
  → Execution: POST /execution/run → ExecutorRunner.start_execution
```

---

## 二、Generate Map 阶段

**前端**：点击 Generate Map → `generateTimetable()`

### 2.1 POST `/api/execution/generate-from-plan`

- **入参**：`{ planId }`
- **逻辑**：`monitor.from_plan.build_execution_from_plan(plan)`
  - 提取原子任务（有 input/output 的任务）
  - 依赖解析：继承祖先的跨子树依赖 + 非原子依赖下沉为原子后代
  - 拓扑排序分 stage（`tasks.task_stages.compute_task_stages`）
  - 写入 `db/{plan_id}/execution.json`

### 2.2 POST `/api/monitor/timetable`

- **入参**：`{ execution, planId }`
- **逻辑**：`monitor.build_layout_from_execution(execution)` → `ExecutorRunner.set_layout(layout, plan_id, execution)`
  - 生成 grid（stage 列）+ isolatedTasks + treeData
  - 将 layout 与 execution 写入 runner 的 `chain_cache`、`timetable_layout`、`plan_id`

---

## 三、Execution 阶段

**前端**：点击 Execution → `runExecution()`

### 3.1 前置检查

- `api.loadExecution()`（GET `/api/execution?planId=xxx`）检查当前 plan 是否有 execution

### 3.2 POST `/api/execution/run`

- **入参**：无（使用 runner 中由 timetable 设置的 `plan_id` 与 `chain_cache`）
- **逻辑**：`ExecutorRunner.start_execution(api_config)`

### 3.3 单任务执行流程（`_execute_task`）

| 步骤 | 说明 |
|------|------|
| 1. 分配 Executor | 从 7 个 worker 池取空闲 |
| 2. 解析输入 | `resolve_artifacts`：从 `db/{plan_id}/{dep_id}/output.json` 读取依赖产出 |
| 3. 执行任务 | `execute_task`：LLM 根据 description、input/output spec 生成结果 |
| 4. 保存产出 | `save_task_artifact` 写入 `db/{plan_id}/{task_id}/output.json` |
| 5. 分配 Validator | 从 5 个 worker 池取空闲 |
| 6. 验证 | 按 task 的 `validation.criteria` 校验（当前实现见下方说明） |
| 7. 状态更新 | `undone` → `doing` → `validating` → `done` / `execution-failed` / `validation-failed` |

### 3.4 调度与重试

- **调度**：依赖满足后调度，同 stage 可并行
- **失败重试**：单任务最多重试 3 次（`MAX_FAILURES`）
- **Rollback**：超过重试次数则回滚该任务及其下游依赖任务

---

## 四、模块与文件

| 文件 | 用途 |
|------|------|
| runner.py | ExecutorRunner：调度、worker 分配、状态持久化、WebSocket 推送 |
| execution/llm_executor.py | LLM 执行任务（支持 Mock） |
| execution/artifact_resolver.py | 从依赖任务解析 input artifacts |
| __init__.py | executor_manager、validator_manager 工作池（7 Executor、5 Validator） |

---

## 五、数据依赖

- **plan_id**：由 `/monitor/timetable` 设置，`/execution/run` 不接收 plan_id
- **chain_cache**：来自 `set_layout`，包含 task_id、dependencies、status、input、output、validation
- **Artifact**：按 `output.artifact` 从 `db/{plan_id}/{task_id}/output.json` 读取

---

## 六、当前实现说明

| 模块 | 实现 | 备注 |
|------|------|------|
| Executor | `llm_executor.execute_task` | 真实 LLM 调用，支持 useMock |
| Validator | 随机模拟 | `runner.py` 中 `validation_passed = random.random() < 0.95`，未按 criteria 校验 |
| Artifact 解析 | `output.artifact` 映射 | 依赖任务的 output 需定义 artifact 名称 |

---

## 七、改进规划

Executor 升级为 Agent、接入 Agent Skills、Atomicity 与能力边界联动等规划详见 [EXECUTOR_IMPROVEMENTS.md](EXECUTOR_IMPROVEMENTS.md)。
