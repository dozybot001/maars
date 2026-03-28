# Research 阶段工作流

Research 是 pipeline 的核心阶段，将原先独立的 Plan 和 Execute 合并为一个迭代循环。

## 整体流程

```
                    ┌──────────────┐
                    │  Calibrate   │ Phase 0: LLM/Agent 自评能力边界
                    └──────┬───────┘
                           ↓
                    ┌──────────────┐
                    │  Decompose   │ Phase 1: 递归分解为原子任务 DAG
                    └──────┬───────┘
                           ↓
              ┌────────────────────────┐
              │  Execute + Verify      │ Phase 2: 拓扑排序，并行执行
              │                        │
              │  对每个任务:            │
              │  execute → verify      │
              │    ├─ pass → 保存       │
              │    ├─ retry → 重试 1 次 │
              │    └─ redecompose → ──────→ 拆分为子任务，re-batch
              └────────────┬───────────┘
                           ↓
                    ┌──────────────┐
                    │  Evaluate    │ Phase 3: 结果是否充分？
                    └──────┬───────┘
                     ↙          ↘
              satisfied      not satisfied
                 ↓                ↓
              完成         基于反馈补充分解 → 回到 Phase 2
```

## Phase 0: Calibrate — 动态能力校准

**目标**：让 LLM/Agent 根据自身能力和研究主题，定义"原子任务"的边界。

**为什么不用静态定义**：
- 不同模式能力差异大（纯文本 vs 有工具的 Agent）
- 同一模式下，不同研究主题的复杂度不同
- Agent 的实际工具可用性需要运行时探测

**实现**：

```python
# research.py
async def _calibrate_atomic_definition(self, idea, my_run_id):
    capabilities = self.llm_client.describe_capabilities()
    # 通过 stream() 调用 — Agent 模式下是完整 agent session
    messages = [
        {"role": "system", "content": _CALIBRATE_SYSTEM},
        {"role": "user", "content": f"## Your Capabilities\n{capabilities}\n\n## Research Topic\n{idea}"},
    ]
    response = await self._stream_llm(self.llm_client, messages, ...)
    return response
```

**关键设计**：calibration 通过 `self.llm_client.stream()` 执行。在 Agent 模式下，这就是一次完整的 agent session——agent 可以实际调用工具（例如搜一下试试）来评估自己的能力边界。

**能力描述链**：

| Client | `describe_capabilities()` 返回 |
|--------|-------------------------------|
| GeminiClient | 继承默认: "Text-only LLM. No tools." |
| AgentClient | "AI Agent (ADK). Model: gemini-2.0-flash\nTools:\n- google_search\n- code_execute\n- ..." |
| AgnoClient | "AI Agent (Agno). Model: Gemini\nTools:\n- websearch\n- arxiv_tools\n- ..." |

**calibration 输出示例（Agent 模式）**：
```
ATOMIC DEFINITION:
单个 Agent session 可完成：一种算法的实现+测试+分析、一个领域的文献综述、
一组实验的运行+结果解读。

需要分解的情况：涉及 3 种以上独立算法的对比分析（每种算法应独立实现测试）、
跨多个不同领域的调研（每个领域应独立调研）。

对于本研究（ODE 数值求解器对比），每种求解器的实现和测试应为独立原子任务，
最终的横向对比分析也应为独立任务。
```

## Phase 1: Decompose — 递归任务分解

使用 calibrated 的原子定义，递归分解研究 idea 为任务 DAG。

**算法**：

1. 根节点 = 研究 idea（id="0"）
2. 对每个 pending 任务，LLM 判断：atomic 或 decompose
3. decompose → 创建子任务，子任务 ID 层级化（`1` → `1_1`, `1_2`）
4. 同层子任务并行处理（`asyncio.gather`）
5. 深度上限 10 层，超限自动标记 atomic
6. 最终输出：flat_tasks（带依赖的原子任务列表）+ tree（嵌套树，供前端渲染）

**依赖规则**：
- 依赖仅限同层兄弟节点
- 无循环依赖
- 最大化并行：仅在真正需要前序输出时才添加依赖

## Phase 2: Execute + Verify — 执行与三路验证

### 执行

任务按拓扑排序分批并行执行：

```python
batches = topological_batches(all_tasks)
# batch 1: [task_1, task_2]       # 无依赖，并行执行
# batch 2: [task_3]               # 依赖 task_1
# batch 3: [task_4, task_5]       # 依赖 task_3
```

每个任务的 prompt 构建：

- **Gemini 模式**：依赖任务的完整输出预加载到 prompt
- **Agent 模式**：仅列出依赖 ID，Agent 通过 `read_task_output` 工具自主读取
- **Redecompose 子任务**：额外注入父任务的 partial output 作为参考

### 三路验证

每个任务执行后，由 verify LLM 判断结果质量。verify 返回三种结果：

```json
// 1. 通过 — 保存结果，继续下一个任务
{"pass": true, "summary": "..."}

// 2. 小问题 — 格式/细节/深度不足，方法正确 → retry 1 次
{"pass": false, "redecompose": false, "review": "输出缺少数据来源引用"}

// 3. 根本性问题 — 任务太大/方法错误 → 跳过 retry，直接拆分
{"pass": false, "redecompose": true, "review": "任务涉及三个独立领域，单次执行无法覆盖"}
```

**判断标准**（写入 verify prompt）：

`redecompose=true` 仅当：
- 任务覆盖多个独立子目标，结果对每个都浅尝辄止
- 结果显示任务范围超出单次 session 能力
- 方法论根本错误（不是仅仅不完整）

### 重试流程

```
execute → verify
  ├─ pass=true → 保存
  ├─ redecompose=true → _RedecomposeNeeded 异常
  └─ redecompose=false → retry with review feedback
       → verify again
         ├─ pass=true → 保存
         ├─ redecompose=true → _RedecomposeNeeded 异常
         └─ redecompose=false → 标记 failed，抛出 RuntimeError
```

## Redecompose — 运行时任务拆分

当 verify 判定 `redecompose=true`，触发运行时重新分解。

### 流程

```
任务 2_1 执行失败（redecompose=true）
  ↓
_redecompose_task():
  1. 保存 partial output 到 _partial_outputs[2_1]
  2. 构造 decompose context:
     "## 原始任务 [2_1]\n{description}\n
      ## 已有执行结果（不充分）\n{partial_output}\n
      ## 审查反馈\n{review}\n
      请将此任务拆分为子任务。已有结果中合格的部分不需要重做。"
  3. 调用 decompose() → 返回子任务
  4. 重编号: 2_1_d1, 2_1_d2, 2_1_d3（d = decomposed，避免 ID 冲突）
  5. 子任务继承父任务的依赖
  6. 注册 _redecompose_parent[2_1_d1] = "2_1"
  ↓
_execute_all_tasks():
  1. 从 _all_tasks 中移除任务 2_1
  2. 插入子任务 2_1_d1, 2_1_d2, 2_1_d3
  3. break 当前 batch 循环
  4. 重新 topological_batches() → 重新编排
  5. 已完成的任务通过 _task_results 跳过
```

### Partial Output 传递

子任务执行时自动注入父任务的部分输出：

```python
# _execute_task() 中
parent_id = self._redecompose_parent.get(task_id)  # "2_1_d1" → "2_1"
prior_attempt = self._partial_outputs.get(parent_id, "")

# 注入 execute prompt
messages = _build_execute_prompt(task, dep_outputs, prior_attempt)
```

子任务 prompt 中的呈现：

```
## Prior attempt on parent task (reference only — focus on YOUR specific subtask):
{partial output from parent task 2_1}
---
## Your task [2_1_d1]:
{specific subtask description}
```

### 子任务 ID 与依赖

| 原任务 | 子任务 | 依赖继承 |
|--------|--------|---------|
| `2_1` (deps: `[1_1]`) | `2_1_d1` (no internal deps) | `[1_1]` ← 继承父依赖 |
| | `2_1_d2` (deps: `[2_1_d1]`) | `[2_1_d1]` ← 内部依赖 |
| | `2_1_d3` (no internal deps) | `[1_1]` ← 继承父依赖 |

规则：有内部依赖的子任务使用内部依赖；没有内部依赖的子任务继承父任务依赖。

## Phase 3: Evaluate — 结果评估

所有任务执行完毕后（如果 max_iterations > 1），评估结果是否充分覆盖研究目标：

```json
// 满足
{"satisfied": true}

// 不满足 → 基于反馈生成新任务
{"satisfied": false, "feedback": "缺少误差分析", "suggestions": ["补充数值误差的理论分析"]}
```

不满足时：
1. 将 feedback + suggestions 作为新的 idea 输入 decompose()
2. 新任务 ID 加 `r{round}_` 前缀避免冲突
3. 新旧任务合并，回到 Phase 2 执行

## Checkpoint Resume

Research 阶段支持断点续传：

```
中断 → Resume:
  1. _load_checkpoint(): 扫描 tasks/*.md，加载已完成任务到 _task_results
  2. 从 DB 读取 plan.json（如果存在）
  3. topological_batches() 重算（确定性）
  4. 跳过 _task_results 中已有的任务
  5. 从断点继续执行

Retry:
  1. 清空 _task_results, _task_summaries, _all_tasks
  2. 清空 _partial_outputs, _redecompose_parent
  3. 删除 DB 中的 tasks/*.md 和 plan.json
  4. 完全从头开始（重新 calibrate + decompose）
```

## 前端任务状态

每个任务在执行过程中会经历以下状态（通过 SSE `task:state` 事件推送）：

| 状态 | CSS class | 含义 |
|------|-----------|------|
| pending | `exec-pending` | 等待执行 |
| running | `exec-running` | 正在执行 |
| verifying | `exec-verifying` | 正在验证 |
| retrying | `exec-retrying` | 验证失败，重试中 |
| decomposing | `exec-decomposing` | 验证判定需要拆分，正在分解 |
| completed | `exec-completed` | 执行完成 |
| failed | `exec-failed` | 最终失败 |
