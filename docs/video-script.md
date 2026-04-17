# MAARS — Video Script (~2.5 min)

> 每行末尾 `·` = 按一次空格。`· ↓` = 按完页面会滚动或高亮切换。

---

Welcome to MAARS — Multi-Agent Automated Research System. `·`\
You give it a research idea — you get back a paper, with real experiments, real code, and real figures, generated from scratch by a pipeline of collaborating LLM agents. `· ↓ scroll → Pipeline`

---

Three stages: Refine sharpens the idea, Research runs the experiments, and Write produces the paper. `· ↓ highlight Refine`

---

In Refine, Explorer surveys the literature and drafts a proposal; Critic reviews it — iterating under the IterationState pattern until zero issues remain. `· ↓ highlight Research`

---

Research is the core engine — where agents actually run experiments and produce results. `·`\
Calibrate defines what an atomic task looks like; Strategy drafts the plan; Decompose splits it into a dependency DAG, executed in parallel topological batches. `·`\
Verify reviews each result — pass, retry, or redecompose — forwarding partial outputs. Evaluate is biased toward stopping, only looping back when it finds a critical gap. `· ↓ highlight Write`

---

Writer drafts, Reviewer critiques — same IterationState pattern — until zero issues remain. A final Polish pass refines the prose and appends a metadata appendix: tokens, timings, model versions. `· ↓ scroll → Architecture`

---

Under the hood: a FastAPI server streams progress over SSE, a Python orchestrator drives the stage sequence, agents run on Agno with Gemini, and all state lives in a plain file-based session directory — no database, fully reproducible. `· ↓ scroll → Showcase / Lorenz`

---

Real output: a one-line prompt — solve the Lorenz system. MAARS returned a complete paper with derivations and four publication-quality plots. `·`\
Eleven minutes. 347k tokens. `· ↓ scroll → Showcase / CIFAR`

---

Harder: does transfer learning weaken a backdoor watermark? MAARS designed the protocol, ran experiments on CIFAR-10 and CIFAR-100, and delivered the figures. `·`\
Three hours. 2.47 million tokens. `· ↓ scroll → Demo video`

---

Here's a live screen recording of a complete MAARS run — I'll scrub through so you can see the timeline. `· ↓ scroll → Docs`

---

Full documentation is at dozybot001.github.io/MAARS. `·`

---

One command: bash start.sh — environment, Docker image, server on localhost:8000. Paste your idea and press Enter. `·`\
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
