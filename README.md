# MAARS

Multi-Agent Automated Research System — an end-to-end research pipeline from a vague idea to a paper draft, powered by four AI Agents.

[中文版 README](README_CN.md) | **English**

---

## Quick Start

**Prerequisites**: Python 3.10+

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn main:asgi_app --host 0.0.0.0 --port 3001 --loop asyncio --http h11
```

Or use the launch script at the project root: `./start.sh` (macOS/Linux) or `start.bat` (Windows).

Open <http://localhost:3001> to access the homepage.

---

## Workflow

A **Research** is the top-level work unit. Each Research corresponds to a research topic and progresses through four stages: refine, plan, execute, and paper.

```text
Enter prompt on homepage -> Create Research -> Enter detail page -> Run full pipeline or stage-by-stage
```

| Page | Description |
| --- | --- |
| **Home** (`/` or `index.html`) | Enter a research topic, click Create to start a Research |
| **Research List** (`research.html`) | View all Researches, click to enter details |
| **Research Detail** (`research_detail.html?researchId=xxx`) | Execute the four stages: refine / plan / execute / paper |

| Stage | Purpose |
| --- | --- |
| Refine | Extract keywords, search arXiv, generate refined idea |
| Plan | Decompose the idea into an executable task tree |
| Execute | Run atomic tasks in parallel, validate outputs |
| Paper | Generate a paper draft from Plan and Task outputs (Markdown/LaTeX) |

Each stage supports **Run** (start fresh), **Resume** (continue from stopped/failed), **Retry** (clear and restart), and **Stop** (abort).

The Thinking panel shows reasoning traces; the Output panel shows final artifacts (literature, task outputs, paper).

---

## Four Agents

| Agent | Responsibility |
| --- | --- |
| Idea | Keyword extraction, arXiv search, Refined Idea generation |
| Plan | Task decomposition (atomicity -> decompose -> format -> quality) |
| Task | Atomic task execution and validation |
| Paper | Paper draft generation (Markdown/LaTeX) |

Each Agent supports three modes: **Mock** (simulated), **LLM** (single-turn), and **Agent** (tool-use loop). Switch modes in Settings -> AI Config. The Paper Agent's Agent mode is currently an MVP: outline -> sections -> assembly.

---

## Configuration

**Alt+Shift+S** (Win/Linux) or **Cmd+Shift+S** (Mac) to open Settings:

- **Theme** — Light / Dark / Black
- **AI Config** — Agent mode, Idea RAG, Self-Reflection, API Preset
- **Data** — Restore recent plan, Clear all data

---

## Project Structure

```text
maars/
├── backend/           # FastAPI + SSE realtime event bridge
│   ├── api/           # Routes (idea, plan, execution, paper, research, session, settings, ...)
│   ├── idea_agent/    # Idea Agent
│   ├── plan_agent/    # Plan Agent
│   ├── task_agent/    # Task Agent (ExecutionRunner + 5 function modules + DI)
│   ├── paper_agent/   # Paper Agent
│   ├── validate_agent/# Step-B contract review (Task Agent sub-component)
│   ├── shared/        # LLM client, constants, reflection, utilities
│   ├── visualization/ # Execution graph layout computation
│   └── db/            # SQLite persistence (Research metadata + sandbox)
├── frontend/          # Static pages, SSE/EventSource, vanilla JS
│   ├── index.html     # Homepage (create Research)
│   ├── research.html  # Research list
│   └── research_detail.html  # Research detail (four-stage execution)
├── ARCHITECTURE.md    # Detailed architecture documentation
└── start.sh / start.bat  # Launch scripts
```

---

## Documentation

| Document | Description |
| --- | --- |
| [Architecture](docs/architecture.md) | System architecture overview ([中文](docs/architecture_cn.md)) |
| [docs/README.md](docs/README.md) | Documentation index |
| [docs/DEVELOPMENT_GUIDE.md](docs/DEVELOPMENT_GUIDE.md) | Development guide (architecture, Research API, Skill system) |
| [docs/workflow/](docs/workflow/) | Workflow docs (user flow, Research pipeline, four Agents, realtime events) |
| [docs/FRONTEND_SCRIPTS.md](docs/FRONTEND_SCRIPTS.md) | Frontend scripts and module dependencies |
| [docs/RELEASE_NOTE_STANDARD.md](docs/RELEASE_NOTE_STANDARD.md) | Release note writing standard |
