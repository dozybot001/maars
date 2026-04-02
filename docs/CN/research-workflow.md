# Research 工作流设计

> 本文聚焦于 MAARS Research 阶段的工作流设计，解释每个环节的输入输出、设计决策和反馈机制。

## 全局流程

```
Calibrate → Strategy → Decompose → Execute ⇄ Verify → Evaluate
                                                          ↓
                                              Strategy Update → Decompose · round N → Execute ...
```

Research 工作流分为两个阶段：**准备阶段**（一次性）和**迭代阶段**（可循环）。

## 1. 准备阶段

### 1.1 Calibrate — 校准原子任务粒度

| | 说明 |
|---|---|
| **目的** | 定义"原子任务"的边界——单次 agent session 能可靠完成的最小工作单元 |
| **输入** | 确定性能力画像（沙箱超时/内存/工具列表）+ 数据集信息 + 研究课题 |
| **输出** | 3-5 句原子定义文本，注入后续 Decompose 的 system prompt |
| **存储** | `calibration.md` |

**设计决策**：能力画像从 config 确定性生成（同配置 = 同输出），LLM 只基于这些具体约束做课题特定的微调。这比让 LLM 凭空想象"什么是原子任务"稳定得多。

### 1.2 Strategy — 研究策略

| | 说明 |
|---|---|
| **目的** | 搜索最佳实践和获胜方案，产出技术策略文档 |
| **输入** | 能力画像 + 数据集 + Calibrate 的原子定义 + 研究课题 |
| **输出** | 策略文档（关键洞察 / 推荐方案 / 陷阱 / 目标指标）+ `score_direction` |
| **存储** | `strategy.md` + `meta.json` 的 score_direction |
| **工具** | DuckDuckGo、arXiv、Wikipedia |

**设计决策**：Strategy 接收能力画像和原子定义，确保推荐的方案在 agent 能力范围内。不会推荐 4g 内存跑不了的深度学习模型。

### 1.3 Decompose — 任务分解

| | 说明 |
|---|---|
| **目的** | 将研究课题递归分解为原子任务 DAG |
| **输入** | 研究课题 + atomic_definition + strategy（注入 system prompt） |
| **输出** | 扁平任务列表 + 树结构 |
| **存储** | `plan_list.json` + `plan_tree.json` |

**核心机制**：

- **递归分解**：每个节点由 LLM 判断是否为原子任务，非原子则拆分为子任务，直到所有叶子都是原子
- **兄弟上下文**：每个节点分解时能看到同级兄弟任务，避免产出重复子任务（如"训练 CatBoost"已存在时不会重复创建）
- **`root_id` 参数**：`decompose()` 支持在任意节点上启动分解。初始分解用 `root_id="0"`，重分解用 `root_id=task_id`，ID 和依赖自动命名，零重映射
- **拓扑排序**：原子任务按依赖关系分 batch，最大化并行度

## 2. 迭代阶段

### 2.1 Execute — 任务执行

| | 说明 |
|---|---|
| **目的** | 逐 batch 执行原子任务 |
| **输入** | 任务描述 + 沙箱约束 + 依赖任务摘要 |
| **输出** | Markdown 结果 + artifacts 文件 + SUMMARY 行 |
| **存储** | `tasks/{id}.md` + `artifacts/{id}/` |
| **工具** | code_execute、list_artifacts、read_task_output、搜索工具 |

**执行模型**：

```
batch 1: [task_1, task_2]  → asyncio.gather（受 API semaphore 限制）
batch 2: [task_3]          → 依赖 batch 1 完成
...
```

- **Semaphore 原子化**：每个任务的 execute→verify→retry→verify 在单个 semaphore 持有期内完成，避免 verify 被其他任务的 execute 插队
- **SUMMARY 行**：Execute agent 在输出末尾写 `SUMMARY:` 行，成为下游任务的依赖摘要。执行者最了解自己做了什么
- **依赖摘要注入**：`build_execute_prompt` 将依赖任务的 SUMMARY 直接放入 prompt，减少 `read_task_output` 调用

### 2.2 Verify — 产出验证

| | 说明 |
|---|---|
| **目的** | 验证任务是否真正产出了预期的制品 |
| **输入** | 任务描述 + 执行结果 |
| **输出** | JSON `{pass, review, redecompose}` |
| **工具** | list_artifacts（验证文件是否存在） |

**三条分支**：

| 结果 | 行为 |
|---|---|
| `pass=true` | 保存结果，继续下一个任务 |
| `pass=false, redecompose=false` | Retry 一次（携带 review 反馈），再次 verify |
| `pass=false, redecompose=true` | 调用 `decompose(root_id=task_id)` 将任务拆分为子任务 |

**设计决策**：
- Verify 不写 summary（由 Execute 负责）
- Verify 被鼓励调用 `list_artifacts` 确认文件存在
- JSON 解析失败时 fallback 为 `pass=False`，不放过质量问题
- 最多 1 次 retry，第二次仍失败则 task failed

### 2.3 Evaluate — 评估与迭代决策

| | 说明 |
|---|---|
| **目的** | 分析已完成工作，决定是否继续迭代 |
| **输入** | 研究目标 + 当前策略 + 分数趋势 + 历史评估 + 能力画像 + 任务摘要 |
| **输出** | JSON `{feedback, suggestions, strategy_update?}` |
| **存储** | `evaluations/eval_v{N}.json` + `evaluation.md` |
| **工具** | read_task_output、list_artifacts |

**迭代控制**：由 Evaluate LLM 自主决定，而非硬编码分数阈值：
- 输出包含 `strategy_update` → 继续迭代
- 不包含 `strategy_update` → 停止

**设计决策**：
- 传入历史评估，附标注"已尝试过——不要重复"
- 传入能力画像，让评估器知道建议的可行性
- 传入当前策略，让评估器能判断策略是否需要调整

### 2.4 Strategy Update — 策略更新

| | 说明 |
|---|---|
| **目的** | 基于评估反馈更新研究策略 |
| **输入** | 旧策略 + 评估反馈 + 建议 + strategy_update 方向 |
| **输出** | 新策略文档 |
| **存储** | `strategy.md`（覆盖） |
| **工具** | DuckDuckGo、arXiv、Wikipedia |

复用 `STRATEGY_SYSTEM` prompt，通过 `build_strategy_update_user` 注入旧策略和评估上下文。

### 2.5 Decompose · round N — 新一轮分解

基于新策略和已完成工作上下文（`_build_iteration_context`），调用标准 `decompose()` 产出补充任务。新任务以 `r{N}_` 前缀命名，作为子树追加到现有分解树。

## 3. 信息流总览

```
Calibrate ──atomic_definition──→ Strategy
                                    │
Strategy ──strategy──→ Decompose ──flat_tasks──→ Execute
                                                    │
Execute ──SUMMARY──→ dep_summaries（下游任务）
Execute ──result──→ Verify
                       │
                  ┌────┴────┐
                  pass     fail
                  │         │
              _save_task   retry / redecompose
                  │
                  ↓
Evaluate ←─ task_summaries + scores + strategy + history
    │
    ├── strategy_update → Strategy Update → Decompose · round N → Execute ...
    └── no update → 结束
```

## 4. Prompt 架构

```
prompts.py          ← 分发层：根据 output_language 选择
prompts_zh.py       ← 全中文指令 + _PREFIX（"所有输出使用中文撰写"）
prompts_en.py       ← 全英文指令 + _PREFIX（"Write ALL output in English"）
```

每个 prompt 文件包含：
- `_PREFIX`：全局指令（自动化模式 + 语言）
- System prompts：`CALIBRATE_SYSTEM`、`STRATEGY_SYSTEM`、`EXECUTE_SYSTEM`、`VERIFY_SYSTEM`、`EVALUATE_SYSTEM`、`DECOMPOSE_SYSTEM_TEMPLATE`
- Builder 函数：`build_execute_prompt`、`build_verify_prompt`、`build_retry_prompt`、`build_evaluate_user`、`build_strategy_update_user`、`build_decompose_system`、`build_decompose_user`

指令语言与输出语言一致，避免混搭导致的 LLM 混乱。

## 5. 与旧架构的关键差异

| 维度 | v12（旧） | v13（新） |
|------|-----------|-----------|
| 能力校准 | LLM 凭空想象原子边界 | 确定性能力画像 + LLM 微调 |
| 策略 | 不知道执行约束 | 接收能力画像和原子定义 |
| 分解 | 子节点看不到兄弟 | 兄弟上下文注入，避免重复 |
| 重分解 | 独立 ID 映射 + 50 行补丁代码 | `decompose(root_id)` 直接复用 |
| 执行 | verify 写 summary | execute 写 SUMMARY 行，verify 只做工具验证 |
| 依赖上下文 | 只传 ID，agent 需 read_task_output | 传入依赖摘要，减少工具调用 |
| 迭代控制 | 硬编码分数阈值 + Replan 追加任务 | Evaluate 自主决定 + Strategy Update + 完整 Decompose |
| Prompt 语言 | 英文指令 + 中文输出要求混搭 | 全中文 / 全英文可切换 |
| 验证 fallback | `pass=True`（放过） | `pass=False`（不放过） |
