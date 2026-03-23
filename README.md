# MAARS

[中文](README_CN.md) | English

**Multi-Agent Automated Research System** — From a single idea to a complete research paper, fully automated.

## What it does

You type a research idea. MAARS runs a 4-stage pipeline and produces a structured paper:

```
Idea → Refine → Plan → Execute → Write → Paper
```

Each stage is powered by LLM calls or autonomous agents. The system decomposes your idea into atomic tasks, executes them (with dependency-aware parallelism and verification), and synthesizes the results into an academic paper.

## Three modes

| Mode | How it works | When to use |
|------|-------------|-------------|
| **Mock** | Replays recorded LLM outputs | Development, UI testing |
| **Gemini** | Direct Google Gemini API calls | Fast, structured LLM pipeline |
| **Agent** | Google ADK agents with ReAct loops | Autonomous reasoning with tool use |

Switch with one line in `.env`:

```env
MAARS_LLM_MODE=mock      # or gemini, or agent
MAARS_GOOGLE_API_KEY=your-key
```

## Architecture

```
Frontend (Vanilla JS)          Backend (FastAPI)
┌─────────────────────┐       ┌──────────────────────────────┐
│ Input + 4 Stage Cards│       │ pipeline/                    │
│ LLM Output Log (L)  │◄─SSE──│   stage.py    (BaseStage)    │
│ Process & Output (R) │       │   orchestrator.py            │
└─────────────────────┘       │   refine.py / plan.py        │
                               │   execute.py / write.py      │
                               ├──────────────────────────────┤
                               │ llm/          (LLMClient ABC)│
                               ├──────────────────────────────┤
                               │ mock/    gemini/    agent/    │
                               │ (modes — swap via config)     │
                               └──────────────────────────────┘
```

**Key design decisions:**
- **`llm/` → `pipeline/` → `mode/`**: three-layer decoupling. Pipeline never knows which mode is active.
- **Unified `call_id` streaming**: every LLM call (sequential or parallel) emits tagged chunks. Frontend routes by `call_id`.
- **String in, string out**: stages communicate via `stage.output`. No shared memory needed.

## Pipeline stages

### Refine
3 rounds: **Explore** → **Evaluate** → **Crystallize**. Turns a vague idea into a structured research proposal.

### Plan
Recursive decomposition into atomic tasks with a dependency DAG. Parallel batch processing. Depth-limited (default 3). Dependency resolution via inherit + expand algorithm.

### Execute
Topological sort → parallel batch execution → verification → optional retry. Each task result stored in file DB. Dependency outputs injected as context.

### Write
Outline → section-by-section writing → polish. Each section only receives its relevant task outputs, keeping prompts focused.

## Quick start

```bash
git clone https://github.com/dozybot001/MAARS.git
cd MAARS
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Configure
cp .env.example .env  # add your API key

# Run
uvicorn backend.main:app --host 0.0.0.0 --port 8000
# Open http://localhost:8000
```

## Frontend

Dual-panel workspace:
- **Left**: LLM Output Log — streaming output with collapsible stage sections
- **Right**: Process & Output — decomposition tree, execution progress, file icons for refined idea and paper

No build step. Vanilla HTML/CSS/JS with ES modules.

## File DB

Each research run creates a timestamped folder:

```
research/20260323-210300-how-does-framing-effect-in/
├── idea.md              # Original input
├── refined_idea.md      # Refine output
├── plan.json            # Flat atomic task list
├── plan_tree.json       # Full decomposition tree
├── paper.md             # Final paper
└── tasks/
    ├── 1_1.md           # Individual task outputs
    ├── 1_2.md
    └── ...
```

## Showcase

Two complete research runs included in `showcase/`:

| Run | Mode | Topic | Tasks |
|-----|------|-------|-------|
| `20260323-210300-*` | Gemini | Cognitive Buffer Hypothesis — cultural modulation of news framing | 31 |
| `20260323-223406-*` | Agent | HMAO — adversarial multi-agent role specialization | 12 |

The semantic history for building MAARS is maintained in the [Intent](https://github.com/dozybot001/Intent) official showcase: [`showcase/maars`](https://github.com/dozybot001/Intent/tree/main/showcase/maars). It captures the MAARS build as 1 intent, 8 snaps, and 3 decisions, covering the path from architecture design to agent mode integration.

## Community

- [Contributing](.github/CONTRIBUTING.md)
- [Code of Conduct](.github/CODE_OF_CONDUCT.md)
- [Security Policy](.github/SECURITY.md)

Issues and pull requests use English templates in GitHub.

## License

MIT
