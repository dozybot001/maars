# MAARS

Multi-Agent Automated Research System — an end-to-end pipeline from a vague idea to a paper draft, powered by four AI Agents.

[中文](README_CN.md) | **English**

## Quick Start

**Prerequisites**: Python 3.10+

```bash
git clone https://github.com/dozybot001/MAARS.git
cd MAARS/backend
pip install -r requirements.txt
python -m uvicorn main:asgi_app --host 0.0.0.0 --port 3001 --loop asyncio --http h11
```

Or use the launch script: `./start.sh` (macOS/Linux) or `start.bat` (Windows).

Open <http://localhost:3001> to access the UI.

## How It Works

Each **Research** progresses through four Agent-driven stages:

| Stage | Agent | What it does |
| --- | --- | --- |
| Refine | Idea | Extract keywords, search arXiv, generate refined idea |
| Plan | Plan | Decompose idea into an executable task tree |
| Execute | Task | Run atomic tasks in parallel, validate outputs |
| Paper | Paper | Generate paper draft (Markdown / LaTeX) |

Each stage supports **Run**, **Resume**, **Retry**, and **Stop**. Agents can operate in Mock, LLM, or Agent mode — configurable in Settings (**Cmd+Shift+S** / **Alt+Shift+S**).

## Documentation

- [Architecture](docs/architecture.md) ([中文](docs/architecture_cn.md))
- [Development Guide](docs/DEVELOPMENT_GUIDE.md)
- [All docs](docs/README.md)
