# Test Utilities

## Mock AI for Planner

Planner uses mock data from `db/test/mock-ai/` (no real API calls).

### Mock Data

Stored in `backend/db/test/mock-ai/`:

- `verify.json` - Atomicity verification responses (keyed by task_id)
- `decompose.json` - Task decomposition responses (keyed by parent task_id)
- `format.json` - Input/output format for atomic tasks (keyed by task_id)

Each entry has `content` (JSON) and `reasoning` (streamed to frontend via `plan-thinking`).

### mock-stream.js

Simulates AI streaming: splits `reasoning` into chunks and emits via `onThinking` with small delays, then returns `content`.
