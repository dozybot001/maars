# Refine / Write Stage Details

[中文](../CN/refine-write.md) | English

> Back to [Architecture Overview](architecture.md)

Refine and Write share the same `TeamStage` base class, driven by an `IterationState` Multi-Agent loop. They are symmetric at the loop level — only configuration differs. Write additionally overrides `_execute()` to run **polish** and **metadata** sub-phases after the Writer/Reviewer loop completes.

## 1. IterationState

```python
@dataclass
class IterationState:
    draft: str              # Latest full content (proposal / paper)
    issues: list[dict]      # [{section, problem, suggestion}]
    iteration: int          # Current round number
    _next_id: int = 1       # Auto-incrementing issue ID counter (I1, I2, I3...)
```

**Update rules**:
- `draft`: Overwritten each round by primary agent output
- `issues`: Reviewer outputs `resolved` list -> remove by system-assigned ID; outputs `issues` list -> system auto-assigns IDs (I1, I2, ...) and appends
- `iteration`: Incremented each round

**Context injection**: IterationState is not agent-visible. It is injected via `_build_primary_prompt()` / `_build_reviewer_prompt()` into user_text. Context size per round is constant (original input + latest draft + unresolved issues), regardless of iteration count.

## 2. Loop Mechanism

```python
for round in range(max_delegations):
    # 1. Primary agent produces/revises
    draft = _stream_llm(primary_agent, input + state)
    state.draft = draft
    save_round_md(primary_dir, draft, round)    # persist
    send()                                       # done signal

    # 2. Reviewer critiques
    review = _stream_llm(reviewer_agent, input + state)
    feedback = parse_json_fenced(review)         # {issues, resolved}
    save_round_md(reviewer_dir, review, round)   # persist
    save_round_json(reviewer_dir, feedback, round)
    send()                                       # done signal

    state.update(draft, feedback)                # issues = drop resolved + auto-assign IDs to new
    if not state.issues: break                   # empty issues list = pass

# If max_delegations reached with issues remaining:
# logs warning and uses last draft (pipeline continues)
```

Two LLM calls per round. Reviewer outputs structured JSON via `_REVIEWER_OUTPUT_FORMAT`. The system — not the reviewer — decides pass by checking if the `issues` list is empty after state update. Runtime mechanically applies state updates and auto-assigns issue IDs (I1, I2, ...) — no LLM involved in state management. When `max_delegations` is reached, the system logs a warning and uses the last draft to continue the pipeline.

## 3. Refine vs Write Configuration

| | Refine | Write |
|---|---|---|
| Primary agent | Explorer (search tools: arXiv, Wikipedia) | Writer (DB tools: list_tasks, read_task_output, list_artifacts) |
| Reviewer agent | Critic (search tools) | Reviewer (DB tools + list_artifacts) |
| Input | `db.get_idea()` raw text | Static instruction (Writer calls tools to read data) |
| Output | `refined_idea.md` | `paper.md` |
| Persistence dirs | `proposals/` + `critiques/` | `drafts/` + `reviews/` |
| SSE phases | `proposal` / `critique` | `draft` / `review` |
| Frontend labels | Proposals / Critiques / Final | Drafts / Reviews / Final |
| Gemini Search | Enabled (`search=True`) | Enabled |

## 4. Typical IterationState Lifecycle

```
Round 1:
  Explorer(idea)                           -> draft v1
  Critic(idea + v1)                        -> {issues:[A,B,C], resolved:[]}
  system auto-assigns IDs: A=I1, B=I2, C=I3
  state = {draft: v1, issues: [I1,I2,I3], iteration: 1, _next_id: 4}
  issues not empty -> continue

Round 2:
  Explorer(idea + v1 + [I1,I2,I3])         -> draft v2
  Critic(idea + v2 + [I1,I2,I3])           -> {issues:[D], resolved:["I1","I2"]}
  system removes I1,I2; auto-assigns D=I4
  state = {draft: v2, issues: [I3,I4], iteration: 2, _next_id: 5}
  issues not empty -> continue

Round 3:
  Explorer(idea + v2 + [I3,I4])            -> draft v3
  Critic(idea + v3 + [I3,I4])              -> {issues:[], resolved:["I3","I4"]}
  system removes I3,I4; no new issues
  state = {draft: v3, issues: [], iteration: 3, _next_id: 5}
  issues empty -> break -> save refined_idea.md / paper.md
```

## 5. Reviewer JSON Format

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

- **No `pass` field** — the system checks if `issues` is empty after state update to decide pass
- **No `id` in issues** — the system auto-assigns IDs (I1, I2, I3...) via `_next_id` counter
- **No `severity`** — all issues are treated equally
- `issues`: New problems found in this round only (the reviewer does NOT repeat unresolved issues)
- `resolved`: System-assigned IDs from the "Previously Identified Issues" section that are now fixed
- `format_issues()` prefixes each issue with its system-assigned `**I{n}**` so the reviewer can reference exact IDs in `resolved`

## 6. Comparison with Research

| | Research | Refine / Write |
|---|---|---|
| Loop | strategy -> decompose -> execute -> evaluate | primary -> reviewer -> primary -> reviewer |
| State | task_results + plan_tree + score | IterationState (draft + issues) |
| Orchestrator | Python `_run_loop` | Python `TeamStage._execute` |
| Agent roles | Independent agent per task | Two fixed roles alternating |
| Communication | Via artifacts/DB | Via IterationState injected into prompt |
| Persistence | Checkpoint/resume | Checkpoint/resume (per-round persistence) |
| Termination | Evaluate has no strategy_update | `issues` list empty after state update, or max_delegations reached (logs warning, uses last draft) |

Core pattern is the same: **Python controls flow, agents execute single steps, state managed at runtime layer.**

## 7. Polish + Metadata Sub-Phases

Polish and metadata are **sub-phases of Write**, not an independent stage. `WriteStage` overrides `TeamStage._execute()`: after the Writer/Reviewer iteration completes and `paper.md` is saved, it runs two additional sub-phases before emitting the stage `done` signal.

**Sub-phase sequence** (inside `WriteStage._execute()`):

1. **Writer/Reviewer loop** — standard `TeamStage` iteration (via `super()`), producing `paper.md`.
2. **`phase='polish'`** — single LLM call with `POLISH_SYSTEM` prompt. Uses `polish_model` (from `MAARS_POLISH_MODEL` → falls back to `write_model` → `google_model`). Reads `paper.md`, emits polished content.
3. **`phase='metadata'`** — deterministic (no LLM). `build_metadata_appendix()` appends a metadata block (timestamps, model info, config, etc.).
4. Saves `paper_polished.md` and emits the Write stage `done` signal.

**Contrast with the Writer/Reviewer loop**:

| | Writer/Reviewer loop | Polish sub-phase | Metadata sub-phase |
|---|---|---|---|
| Trigger | Main TeamStage loop | After loop, `phase='polish'` | After polish, `phase='metadata'` |
| LLM | Iterative, up to `max_delegations` | Single call | None (deterministic) |
| Input | Task data via DB tools | `paper.md` | Polished content + session meta |
| Output | `paper.md` | Polished body | Appended metadata block |
| Final artifact | `paper.md` | (in-memory) | `paper_polished.md` |

Polish exists to handle formatting cleanup, consistency checks, and metadata injection that don't benefit from iterative review. Because it lives inside Write, the frontend progress bar has **no separate "polish" node** — only `refine / calibrate / strategy / decompose / execute / evaluate / write`.

## 8. Code Locations

| File | Role |
|---|---|
| `backend/team/stage.py` | TeamStage base class + IterationState |
| `backend/team/refine.py` | RefineStage configuration |
| `backend/team/write.py` | WriteStage: Writer + Reviewer loop + overridden `_execute()` that runs polish + metadata sub-phases |
| `backend/team/polish.py` | Utility module: `build_polish_input`, `build_metadata_appendix` (NOT a Stage subclass) |
| `backend/team/prompts_en.py` | EN prompts + `_REVIEWER_OUTPUT_FORMAT` + `POLISH_SYSTEM` |
| `backend/team/prompts_zh.py` | ZH prompts |
