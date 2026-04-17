# MAARS — Video Script (~5 min)

> 每行末尾 `·` = 按一次空格。`· ↓` = 按完页面会滚动或高亮切换。

---

Welcome to MAARS — Multi-Agent Automated Research System. `·`
You give it a research idea. You get back a paper — with real experiments, real code, real figures. `·`
Not a summary. Not a template. A complete research artifact, generated from scratch by a pipeline of collaborating LLM agents. `· ↓ scroll → Pipeline`

---

MAARS runs three stages: Refine, Research, and Write. `·`
Each stage has a stable input-output boundary — the Python runtime orchestrates control flow, retries, and persistence; agents handle the open-ended intellectual work. `·`
This separation keeps the system predictable, auditable, and easy to debug. `· ↓ highlight Refine`

---

Refine is where the raw idea gets sharpened into a structured research proposal. `·`
Explorer surveys the literature — ArXiv, Wikipedia, web search — then produces a scoped proposal with a clear research direction. `·`
Critic reviews it, surfacing gaps, ambiguities, and out-of-scope claims. `·`
They iterate under the IterationState pattern: each round, resolved issues are closed and new ones tracked, until the critic has nothing left to flag. `·`
Output: a refined_idea.md that anchors everything downstream. `· ↓ highlight Research`

---

Research is the core engine — the stage where agents actually run experiments and produce results. `·`
It starts with Calibrate: a single LLM call that reads your dataset, your sandbox capabilities, and your research goal, and writes a precise definition of what an atomic task should look like for this specific problem. `·`
Strategy then drafts a high-level research plan and sets a scoring direction — what metric are we optimizing, and which way is better? `·`
Decompose takes the strategy and recursively splits it into a dependency DAG. Each task is judged for atomicity, and sibling judges run in parallel — one failing branch never stalls the rest. `·`
Execute runs tasks in topological batches using asyncio.gather with a semaphore to control concurrency. `·`
Here is a deliberate engineering choice: instead of launching a fresh Docker container per task, MAARS keeps one persistent container alive for the whole session, reusing it via exec_run. Installed packages survive across tasks — eliminating roughly 190 seconds of pip install overhead per task. `·`
Verify reviews each completed task: pass, retry, or redecompose. Redecompose splits a failed task into subtasks and forwards prior partial outputs as context — the system builds on what already worked. `·`
Finally, Evaluate receives all task summaries and score trends, and is deliberately biased toward stopping. It only triggers a new Strategy round when it identifies a critical gap — preventing runaway iteration while still catching genuinely incomplete results. `· ↓ highlight Write`

---

Write takes everything Research produced and turns it into a paper. `·`
Writer reads all the artifacts — code, figures, data, task summaries — and drafts a complete structured paper from scratch. `·`
Reviewer critiques it using the same IterationState pattern as Refine: issues tracked, resolved, iterated until clean. `·`
A final Polish sub-step does one LLM pass for prose quality, then generates a deterministic metadata appendix — token counts, timings, model versions, sandbox config, and a full file manifest. `· ↓ scroll → Architecture`

---

Under the hood, five layers. `·`
The entry layer is a FastAPI server streaming real-time events to a vanilla JS frontend via SSE. `·`
The orchestrator sequences the three stages, manages session recovery, and handles termination. `·`
The stage layer gives ResearchStage and TeamStage a common I/O contract — every stage reads from and writes to a file-based session DB. `·`
Agents run on the Agno framework, powered by Gemini with native Google Search. At the base: ArXiv, Wikipedia, Kaggle, Docker sandbox. `·`
Every run is just a directory: proposals, critiques, plan trees, task outputs, the polished paper, and a reproduce bundle with a Dockerfile. No hidden state — cd in and read everything. `· ↓ scroll → Showcase / Lorenz`

---

Let's look at real outputs. First case: a one-line prompt — solve the Lorenz system and produce four chaos figures. `·`
Out came a complete paper: mathematical derivations, commented Python code, and four publication-quality plots. `·`
The 3D phase-space trajectory. A bifurcation diagram over ρ. A Lyapunov divergence curve. And a stability heatmap across parameter space. `·`
Eleven minutes. 347k tokens. `· ↓ scroll → Showcase / CIFAR`

---

Second case, significantly harder. The research question: does legitimate transfer learning weaken a backdoor watermark embedded in a neural network? `·`
MAARS designed the full experimental protocol from scratch — poisoned a CIFAR-10 source model with a BadNets-style trigger, then fine-tuned it to CIFAR-100 under two strategies: head-only versus full fine-tuning. `·`
It generated the comparative figures, tracked watermark persistence across epochs, and wrote the paper — covering hypothesis, methodology, results, and interpretation. `·`
Three hours. 2.47 million tokens. `· ↓ scroll → Demo video`

---

Here is a live screen recording of a complete MAARS run — the full pipeline from idea to paper. `·`
I'll scrub through so you can see the timeline. `·`
*[拖动进度条展示]* `· ↓ scroll → Docs`

---

Full documentation is on the website. `·`
Architecture — five layers, SSE protocol, storage layout, stage inheritance. `·` *(自动跳转)*
Refine & Write — IterationState pattern, how the Primary ↔ Reviewer loop converges. `·` *(自动跳转)*
Research — every phase from Calibrate through Evaluate, with code references. `·` *(自动跳转)* `· ↓ scroll → Quickstart`

---

Getting started takes one command: bash start.sh. `·`
On first run it creates a virtual environment, installs dependencies, and builds the Docker sandbox image. `·`
Then it serves the UI on localhost:8000. `·`
Paste your research idea — plain text, markdown, or a Kaggle competition URL — and press Enter. `·`
MAARS is open source at dozybot001/MAARS. Thanks for watching. `·`

---

## 快速启动

```bash
cd /path/to/MAARS/site
python3 -m http.server 8080
# 浏览器打开 http://localhost:8080/?tp=1
```

## 按键

| 键 | 动作 |
|----|------|
| `Space` | 下一行（`· ↓` 处自动滚动或切换高亮） |
| `←` | 上一行 |
| `H` | 隐藏 / 显示字幕条 |
