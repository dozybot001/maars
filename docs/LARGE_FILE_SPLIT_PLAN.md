# Large File Split Plan

Date: 2026-03-15

## Current oversized core files

Based on a workspace scan of `backend` and `frontend/js`, these are the main files above 300 lines that are part of the active product path:

- `frontend/js/flows/research.js` - 1846 lines
- `backend/task_agent/runner.py` - 1325 lines
- `frontend/js/regions/tree/task-tree.js` - 682 lines
- `backend/api/routes/research.py` - 675 lines
- `backend/task_agent/agent_tools.py` - 824 lines
- `frontend/js/flows/task.js` - 402 lines
- `frontend/js/ui/settings.js` - 358 lines
- `frontend/js/regions/thinking.js` - 325 lines
- `frontend/js/api/api.js` - 313 lines

## Split done in this pass

`frontend/js/flows/research.js`

- Extracted execute-graph payload recovery and rerender scheduling into `frontend/js/flows/research-execution-graph.js`.
- Goal: stop graph rendering logic from continuing to grow inside the main research page controller.
- Rationale: this logic has a distinct lifecycle, minimal backend coupling, and was already becoming a separate concern due to refresh/restore rerender handling.

## Recommended next splits

### 1. `backend/task_agent/runner.py`

Keep `ExecutionRunner` as the orchestration shell, but move internal concerns out by responsibility:

- `backend/task_agent/run_state.py`
  - retry counters
  - attempt history persistence/load/clear
  - task bookkeeping helpers
- `backend/task_agent/event_emitter.py`
  - `_emit`, `_emit_await`, runtime status emission, task state broadcasts
- `backend/task_agent/task_context.py`
  - execution context assembly
  - original validation criteria helpers
  - Step B packet preparation
- `backend/task_agent/task_executor.py`
  - execution + validation pass for a single task
  - retry-or-fail decision path

Why first: `runner.py` is the biggest backend coordination hotspot and currently mixes state model, event transport, persistence, retry logic, and task execution.

### 2. `frontend/js/flows/research.js`

Continue separating by UI domain instead of by utility type:

- `frontend/js/flows/research-stage-controls.js`
  - stage buttons
  - stage status rendering
  - run/resume/retry/stop bindings
- `frontend/js/flows/research-execution-timeline.js`
  - execute timeline state
  - message append/dedupe
  - attempt grouping and stream rendering
- `frontend/js/flows/research-restore.js`
  - `loadResearch`
  - restore snapshot hydration
  - restore-driven rerender triggers

Why this boundary: `research.js` is currently both page controller and execute timeline renderer. The timeline code alone is large enough to evolve independently.

### 3. `frontend/js/regions/tree/task-tree.js`

Split by render surface:

- `frontend/js/regions/tree/task-tree-render.js`
  - layout scaling
  - SVG edge rendering
  - node placement
- `frontend/js/regions/tree/task-tree-popover.js`
  - task detail popover
  - retry/resume action binding
- `frontend/js/regions/tree/task-tree-status.js`
  - aggregate status logic
  - DOM class updates for status sync

Why this boundary: tree rendering and popover behavior change for different reasons and should not share one file.

### 4. `backend/api/routes/research.py`

Split route handlers by stage domain:

- `backend/api/routes/research_lifecycle.py`
- `backend/api/routes/research_refine.py`
- `backend/api/routes/research_execute.py`
- `backend/api/routes/research_paper.py`

Why this boundary: request validation and stage execution endpoints are cohesive by stage, not by one giant route file.

## Guardrails for future splits

- Prefer extracting cohesive behavior with stable inputs/outputs over moving random helper functions.
- Keep browser entrypoints non-module for now unless the frontend script loading strategy is intentionally upgraded.
- For backend splits, preserve `ExecutionRunner` public behavior first and move internals behind delegation.
- After each split, run targeted tests first, then the broader task-agent suite.