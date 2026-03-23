# Contributing

Thank you for your interest in MAARS! Here's how to get started.

### Development Setup

```bash
git clone https://github.com/dozybot001/MAARS.git
cd MAARS
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Run in mock mode (no API key needed):
```bash
uvicorn backend.main:app --reload
```

### Project Structure

```
backend/
├── pipeline/    # Core framework (BaseStage, orchestrator) — mode-agnostic
├── llm/         # LLMClient interface
├── mock/        # Mock mode implementation
├── gemini/      # Gemini mode implementation
├── agent/       # Agent mode implementation (Google ADK)
├── routes/      # FastAPI HTTP/SSE endpoints
└── db.py        # File-based research storage

frontend/
├── index.html   # Single page
├── css/         # Modular CSS (variables, layout, workspace, etc.)
└── js/          # ES modules (events, api, log-viewer, process-viewer, etc.)
```

### Key Principles

1. **Pipeline layer is mode-agnostic.** `pipeline/` must never import from `mock/`, `gemini/`, or `agent/`.
2. **Unified streaming model.** All LLM calls use `call_id`-tagged chunks.
3. **String in, string out.** Stages communicate through `stage.output`.
4. **No build step for frontend.** Vanilla JS/CSS only.

### How to Contribute

1. **Fork** the repository
2. **Create** a feature branch: `git checkout -b feature/your-feature`
3. **Make changes** following the principles above
4. **Test** with mock mode: `MAARS_LLM_MODE=mock uvicorn backend.main:app --reload`
5. **Submit** a Pull Request with a clear description

### Adding a New Mode

Create a new directory under `backend/` (e.g., `backend/openai/`):
1. Implement `LLMClient` interface (see `llm/client.py`)
2. Create `create_xxx_stages()` assembly function
3. Add mode to `main.py` dispatch

### Adding Tools for Agent Mode

Add to `backend/agent/tools/`:
- Shared tools: `tools/shared/`
- Stage-specific tools: `tools/<stage_name>/`
