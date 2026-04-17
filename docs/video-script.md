# MAARS — 3-Minute Video Script (website walkthrough)

> Delivery: screen-record the live website (`?tp=1`), scroll through sections as you speak.
> Controls: **Space** next line · **←** previous · **O** open link · **1/2/3** open doc · **H** hide overlay

---

## [0:00 – 0:15] Hero

Welcome to MAARS — Multi-Agent Automated Research System.
Bring a research idea, walk away with a paper. Fully automated, end-to-end.

## [0:15 – 0:30] Pipeline overview

*(scroll → #pipeline)*

MAARS runs three stages, each with a clean input-output boundary.
The runtime handles control flow and persistence; agents do the open-ended work.

## [0:30 – 0:50] Refine

*(highlight card-refine)*

In Refine, Explorer surveys the literature and drafts a research proposal.
Critic reviews it within scope, surfaces gaps and ambiguities.
They iterate until zero issues remain — the IterationState pattern.

## [0:50 – 2:10] Research

*(highlight card-research)*

Research is the core engine.
Calibrate runs once — one LLM call that defines what an "atomic task" looks like for this specific problem.
Strategy then drafts a research plan and a scoring direction.
Decompose turns that into a dependency DAG. Tasks split recursively; sibling judges run in parallel.
Execute runs tasks in topological batches. Key design: one persistent Docker container stays alive for the whole session — no per-task startup overhead.
Verify returns one of three verdicts: pass, retry, or redecompose.
Redecompose splits a failed task and passes prior partial outputs to the new subtasks — the system refines rather than restarts.
Finally, Evaluate. Biased toward stopping — it only triggers another round when there is a critical gap.

## [2:10 – 2:25] Write

*(highlight card-write)*

Write follows the same IterationState pattern: Writer drafts, Reviewer critiques, loop until zero issues.
A Polish sub-step does one final LLM pass and appends a deterministic metadata appendix — tokens, timings, scores.

## [2:25 – 2:40] Architecture

*(scroll → #architecture)*

Under the hood: five layers — from the FastAPI entry point down to Docker sandboxes and a file-based session DB.
Every run is just a directory of files. No hidden state — you can cd into any session and read exactly what each agent said.

## [2:40 – 2:55] Showcase — Lorenz

*(scroll → #showcase-lorenz)*

Let's look at real outputs. A one-line prompt: solve the Lorenz system and produce four chaos figures.
Out came derivations, code, and four publication-quality plots. Eleven minutes, 347k tokens.

## [2:55 – 3:15] Showcase — CIFAR

*(scroll → #showcase-cifar)*

A harder run: does legitimate fine-tuning erase a backdoor watermark in a neural network?
MAARS designed the experiments, poisoned a CIFAR-10 source model, ran two fine-tuning strategies on CIFAR-100, and delivered the comparative figures that went into the paper.
Three hours. 2.47 million tokens.

## [3:15 – 3:35] Live recording

*(scroll → #screens · press O to open recording)*

Here is a live screen recording of a complete MAARS run.
I'll scrub through to give you a sense of how the system works in real time.
*[scrub the video]*

## [3:35 – 3:50] Docs

*(scroll → #docs · press O for Research doc, 1 for Architecture, 2 for Refine & Write)*

Full documentation is on the website.
The Research doc walks through every phase — Calibrate, Strategy, Decompose, Execute, Verify, Evaluate — with code references.

## [3:50 – 4:00] Quickstart + CTA

*(scroll → #quickstart)*

One command to get started: bash start.sh.
It sets up the environment, builds the Docker image, and serves on localhost:8000.
MAARS is open source at dozybot001/MAARS. Thanks for watching.

---

## Controls cheatsheet

| Key | Action |
|-----|--------|
| `Space` | Next line (auto-scrolls + highlights on segment change) |
| `←` | Previous line |
| `O` | Open link for current segment (recording or doc) |
| `1` | Open Architecture doc |
| `2` | Open Refine & Write doc |
| `3` | Open Research doc |
| `H` | Hide / show overlay |

## Local setup

```bash
cd /path/to/MAARS/site
python3 -m http.server 8080
# open http://localhost:8080/?tp=1
```

## Recording notes

| Time | Screen | Note |
|------|--------|------|
| 0:00–0:15 | Hero | Let the tagline sit before speaking |
| 0:15–0:30 | Pipeline header | Slow scroll across the three cards |
| 0:30–0:50 | card-refine highlighted | Ring appears automatically |
| 0:50–2:10 | card-research highlighted | ~80s — 12s per phase, don't rush |
| 2:10–2:25 | card-write highlighted | |
| 2:25–2:40 | Architecture (5-layer list + file tree) | |
| 2:40–2:55 | Lorenz showcase | Hover over the four figures |
| 2:55–3:15 | CIFAR showcase | |
| 3:15–3:35 | Screens section + recording | Press O, scrub video in new tab |
| 3:35–3:50 | Docs cards | Press O or 1/2/3 to open a doc |
| 3:50–4:00 | Quickstart | End on the copy-command block |

> **Note:** Total ~4 minutes with the live video scrub. Trim if needed by cutting the Architecture section or shortening the recording demo.
