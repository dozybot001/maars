# MAARS — Video Script

> 每行末尾 `·` = 按一次空格。`· ↓` = 按完页面会滚动或高亮切换。
> 快捷键：**O** 打开链接  **1/2/3** 打开文档  **←** 上一行  **H** 隐藏字幕

---

Welcome to MAARS — Multi-Agent Automated Research System. `·`
Bring a research idea, walk away with a paper. Fully automated, end-to-end. `· ↓ scroll → Pipeline`

---

MAARS runs three stages, each with a clean input-output boundary. `·`
The runtime handles control flow and persistence; agents do the open-ended work. `· ↓ highlight Refine`

---

In Refine, Explorer surveys the literature and drafts a research proposal. `·`
Critic reviews it within scope, surfaces gaps and ambiguities. `·`
They iterate until zero issues remain — the IterationState pattern. `· ↓ highlight Research`

---

Research is the core engine. `·`
Calibrate runs once — one LLM call that defines what an "atomic task" looks like for this specific problem. `·`
Strategy then drafts a research plan and a scoring direction. `·`
Decompose turns that into a dependency DAG. Tasks split recursively; sibling judges run in parallel. `·`
Execute runs tasks in topological batches. Key design: one persistent Docker container stays alive for the whole session — no per-task startup overhead. `·`
Verify returns one of three verdicts: pass, retry, or redecompose. `·`
Redecompose splits a failed task and passes prior partial outputs to the new subtasks — the system refines rather than restarts. `·`
Finally, Evaluate. Biased toward stopping — it only triggers another round when there is a critical gap. `· ↓ highlight Write`

---

Write follows the same IterationState pattern: Writer drafts, Reviewer critiques, loop until zero issues. `·`
A Polish sub-step does one final LLM pass and appends a deterministic metadata appendix — tokens, timings, scores. `· ↓ scroll → Architecture`

---

Under the hood: five layers — from the FastAPI entry point down to Docker sandboxes and a file-based session DB. `·`
Every run is just a directory of files. No hidden state — you can cd into any session and read exactly what each agent said. `· ↓ scroll → Showcase / Lorenz`

---

Let's look at real outputs. A one-line prompt: solve the Lorenz system and produce four chaos figures. `·`
Out came derivations, code, and four publication-quality plots. Eleven minutes, 347k tokens. `· ↓ scroll → Showcase / CIFAR`

---

A harder run: does legitimate fine-tuning erase a backdoor watermark in a neural network? `·`
MAARS designed the experiments, poisoned a CIFAR-10 source model, ran two fine-tuning strategies on CIFAR-100, and delivered the comparative figures that went into the paper. `·`
Three hours. 2.47 million tokens. `· ↓ 停留原地`

---

Here is a live screen recording of a complete MAARS run. `·`
I'll scrub through to give you a sense of how the system works in real time. `·`
*[scrub the video — press **O** to open it]* `· ↓ scroll → Docs`

---

Full documentation is on the website. `·`
The Research doc walks through every phase — Calibrate through Evaluate — with code references. `·`
*[press **O** for Research doc, **1** for Architecture, **2** for Refine & Write]* `· ↓ scroll → Quickstart`

---

One command to get started: bash start.sh. `·`
It sets up the environment, builds the Docker image, and serves on localhost:8000. `·`
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
| `Space` | 下一行（`· ↓` 处会自动滚动或切换高亮） |
| `←` | 上一行 |
| `O` | 打开当前 segment 的链接（录像 / 文档） |
| `1` | Architecture 文档 |
| `2` | Refine & Write 文档 |
| `3` | Research 文档 |
| `H` | 隐藏 / 显示字幕条 |
