# Refine / Write 阶段详情

中文 | [English](../EN/refine-write.md)

> 回到 [架构概览](architecture.md)

Refine 和 Write 共享同一个 `TeamStage` 基类，使用 `IterationState` 驱动的 Multi-Agent 循环。循环层面两者对称，仅配置不同。Write 额外覆写了 `_execute()`，在 Writer/Reviewer 循环结束后追加 **polish** 与 **metadata** 两个子阶段。

## 1. IterationState

```python
@dataclass
class IterationState:
    draft: str              # 最新一版完整内容（提案/论文）
    issues: list[dict]      # [{section, problem, suggestion}]
    iteration: int          # 当前轮次
    _next_id: int = 1       # Issue ID 自增计数器（I1, I2, I3...）
```

**状态更新规则**：
- `draft`：每轮由 primary agent 产出，直接覆盖
- `issues`：reviewer 输出 `resolved` 列表 -> 按系统分配的 ID 移除；reviewer 输出 `issues` 列表 -> 系统自动分配 ID（I1, I2, ...）并追加
- `iteration`：每轮 +1

**上下文注入**：IterationState 不是 Agent 可感知的对象，通过 `_build_primary_prompt()` / `_build_reviewer_prompt()` 拼接到 user_text 中。每轮 Agent 收到的上下文大小恒定（原始输入 + 最新 draft + 未解决 issues），不随迭代轮数增长。

## 2. 循环机制

```python
for round in range(max_delegations):
    # 1. Primary agent 产出/修订
    draft = _stream_llm(primary_agent, input + state)
    state.draft = draft
    save_round_md(primary_dir, draft, round)    # 落盘
    send()                                       # done signal

    # 2. Reviewer 评审
    review = _stream_llm(reviewer_agent, input + state)
    feedback = parse_json_fenced(review)         # {issues, resolved}
    save_round_md(reviewer_dir, review, round)   # 落盘
    save_round_json(reviewer_dir, feedback, round)
    send()                                       # done signal

    state.update(draft, feedback)                # issues = 去 resolved + 自动分配 ID 给新 issue
    if not state.issues: break                   # issues 列表为空 = 通过

# 若达到 max_delegations 仍有未解决 issues：
# 记录警告日志，使用最后一版 draft 继续流水线
```

每轮 2 次 LLM 调用。Reviewer 通过 `_REVIEWER_OUTPUT_FORMAT` 输出 JSON 结构化反馈。系统（而非 reviewer）通过检查 `issues` 列表是否为空来判定通过。Runtime 机械执行状态更新并自动分配 issue ID（I1, I2, ...）——状态管理不涉及 LLM。当达到 `max_delegations` 时，系统记录警告日志并使用最后一版 draft 继续流水线。

## 3. Refine vs Write 配置对比

| | Refine | Write |
|---|---|---|
| Primary agent | Explorer（搜索工具：arXiv, Wikipedia） | Writer（DB 工具：list_tasks, read_task_output, list_artifacts） |
| Reviewer agent | Critic（搜索工具） | Reviewer（DB 工具 + list_artifacts） |
| 输入 | `db.get_idea()` 原始文本 | 静态指令（Writer 自己调工具读数据） |
| 输出 | `refined_idea.md` | `paper.md` |
| 落盘目录 | `proposals/` + `critiques/` | `drafts/` + `reviews/` |
| SSE phase | `proposal` / `critique` | `draft` / `review` |
| 前端标签 | Proposals / Critiques / Final | Drafts / Reviews / Final |
| Gemini Search | 启用（`search=True`） | 启用 |

## 4. 典型 IterationState 生命周期

```
Round 1:
  Explorer(idea)                           -> draft v1
  Critic(idea + v1)                        -> {issues:[A,B,C]}
  系统分配 ID: I1=A, I2=B, I3=C
  state = {draft: v1, issues: [I1,I2,I3], iteration: 1, _next_id: 4}

Round 2:
  Explorer(idea + v1 + [I1,I2,I3])         -> draft v2
  Critic(idea + v2 + [I1,I2,I3])           -> {issues:[D], resolved:[I1,I2]}
  系统分配 ID: I4=D；移除 I1, I2
  state = {draft: v2, issues: [I3,I4], iteration: 2, _next_id: 5}

Round 3:
  Explorer(idea + v2 + [I3,I4])            -> draft v3
  Critic(idea + v3 + [I3,I4])              -> {issues:[], resolved:[I3,I4]}
  issues 为空 -> 通过
  break -> save refined_idea.md / paper.md
```

## 5. Reviewer JSON 格式

```json
{
  "issues": [
    {
      "section": "Methodology",
      "problem": "DAG extraction feasibility unclear",
      "suggestion": "Add human-in-the-loop validation step"
    }
  ],
  "resolved": ["I1", "I3"]
}
```

- `issues`：本轮新发现的问题（无需 `id`、`severity`，由系统自动分配 ID）
- `resolved`：引用上方 "Previously Identified Issues" 中已修复的系统分配 ID（如 I1, I3）
- 通过判定：系统在状态更新后检查 `issues` 列表是否为空，为空即通过（无需 `pass` 字段）
- `format_issues()` 输出中每个 issue 以 `**I{n}**` 前缀标识，确保 reviewer 能准确引用

## 6. 与 Research 的对比

| | Research | Refine / Write |
|---|---|---|
| 循环 | strategy -> decompose -> execute -> evaluate | primary -> reviewer -> primary -> reviewer |
| 状态 | task_results + plan_tree + score | IterationState (draft + issues) |
| 编排者 | Python `_run_loop` | Python `TeamStage._execute` |
| Agent 角色 | 每个 task 独立 Agent | 两个固定角色交替 |
| 通信方式 | 通过 artifacts/DB | 通过 IterationState 注入 prompt |
| 持久化 | checkpoint/resume | checkpoint/resume（每轮落盘） |
| 终止条件 | Evaluate 无 strategy_update | issues 列表为空或达到 max_delegations（警告 + 继续） |

核心模式一致：**Python 控制流程，Agent 只负责执行单步，状态在 runtime 层管理。**

## 7. Polish + Metadata 子阶段

Polish 与 Metadata 是 **Write 的子阶段**，不是独立阶段。`WriteStage` 覆写 `TeamStage._execute()`：在 Writer/Reviewer 循环完成、`paper.md` 落盘后，继续执行两个子阶段，然后才发出 stage 的 `done` 信号。

**子阶段顺序**（位于 `WriteStage._execute()` 内部）：

1. **Writer/Reviewer 循环**：标准 `TeamStage` 迭代（通过 `super()` 执行），产出 `paper.md`。
2. **`phase='polish'`**：使用 `POLISH_SYSTEM` prompt 的单次 LLM 调用。使用 `polish_model`（来自 `MAARS_POLISH_MODEL` → 回退到 `write_model` → `google_model`）。读取 `paper.md`,产出润色后的正文。
3. **`phase='metadata'`**：确定性处理（无 LLM）。`build_metadata_appendix()` 追加元数据块（生成日期、模型、配置等）。
4. 保存 `paper_polished.md`，发出 Write stage `done` 信号。

**与 Writer/Reviewer 循环的对比**：

| | Writer/Reviewer 循环 | Polish 子阶段 | Metadata 子阶段 |
|---|---|---|---|
| 触发 | TeamStage 主循环 | 循环结束后，`phase='polish'` | Polish 后，`phase='metadata'` |
| LLM | 迭代，最多 `max_delegations` 轮 | 单次调用 | 无（确定性） |
| 输入 | 通过 DB 工具读取 task 数据 | `paper.md` | 润色后正文 + session meta |
| 输出 | `paper.md` | 润色后正文 | 追加元数据块 |
| 最终产物 | `paper.md` | （内存中） | `paper_polished.md` |

Polish 用于处理格式清理、一致性检查和元数据注入——这些工作并不受益于迭代评审。由于 polish 内嵌在 Write 中,前端进度条 **不包含独立的 "polish" 节点**,仅有 `refine / calibrate / strategy / decompose / execute / evaluate / write`。

## 8. 代码位置

| 文件 | 职责 |
|---|---|
| `backend/team/stage.py` | TeamStage 基类 + IterationState |
| `backend/team/refine.py` | RefineStage 配置 |
| `backend/team/write.py` | WriteStage：Writer + Reviewer 循环 + 覆写 `_execute()` 追加 polish/metadata 子阶段 |
| `backend/team/polish.py` | 工具模块：`build_polish_input`、`build_metadata_appendix`（非 Stage 子类） |
| `backend/team/prompts_en.py` | EN prompts + `_REVIEWER_OUTPUT_FORMAT` + `POLISH_SYSTEM` |
| `backend/team/prompts_zh.py` | ZH prompts |
