# MAARS — 3-Minute Video Script

> Target length: ~3 minutes / ~420 words at ~140 wpm.
> Emphasis: **Research stage** (the most complex). Refine and Write share one critic-loop pattern. Polish is a single LLM pass.

---

## [0:00 – 0:20] Hook

Hi, I'm going to show you **MAARS** — a **Multi-Agent Automated Research System**. You give it a research idea, or even just a Kaggle competition URL, and it returns a polished paper. Real code, real experiments, real numbers — fully automated, end-to-end.

## [0:20 – 0:40] Pipeline at a Glance

MAARS runs four stages: **Refine, Research, Write, Polish.**

Refine and Write share **the same pattern** — a generator agent paired with a critic, looping until the critic finds zero open issues. Polish is just one LLM pass for prose, plus a deterministic metadata appendix you can audit. The real engine — and what I want to focus on today — is **Research**.

## [0:40 – 1:00] Why Research Is Hard

Research is hard because it's **open-ended execution**. You can't just ask an LLM to "do the experiments." You have to plan them, decompose them into runnable units, execute code that actually works, verify the outputs are valid, and decide whether you've learned enough to stop. MAARS handles all of that with a six-phase loop.

## [1:00 – 1:20] Calibrate & Strategy

It begins with **Calibrate** — one LLM call that looks at your sandbox capabilities and your dataset, and writes a definition of what an "atomic task" should look like for *this specific* problem. That definition gets injected into every later prompt.

Then **Strategy** drafts a high-level research plan and a scoring direction — what does success look like, and which way is "better."

## [1:20 – 1:40] Decompose

**Decompose** turns the strategy into an actual task graph. It's recursive: tasks are split, with sibling context, until each leaf matches the Calibrate definition. The result is `plan_tree.json`, a dependency DAG that's the single source of truth for the run. Sibling judges run with `return_exceptions=True`, so one bad branch doesn't kill the whole tree.

## [1:40 – 2:10] Execute — One Persistent Container

Now **Execute**. This is where it gets real. Tasks are scheduled in topological batches and run in parallel with `asyncio.gather`, gated by a semaphore.

Here's a deliberate design choice: instead of spinning up a fresh container per task, MAARS keeps **one persistent Docker container alive for the whole session** and runs every task inside it via `exec_run`. Installed packages, env vars, and temp files survive across calls — which kills roughly 190 seconds of `pip install` overhead *per task*. Configurable CPU, memory, network, and optional GPU passthrough still apply. Code actually runs. Figures actually render. Numbers come from real experiments.

## [2:10 – 2:35] Verify & Evaluate

Every task then goes through **Verify**, which returns one of three verdicts: **pass**, **retry**, or — the interesting one — **redecompose**, which splits the failed task into subtasks, replaces it in the DAG, and reschedules. Crucially, prior partial outputs are passed to the new subtasks, so the system refines instead of restarts.

After the batch finishes, **Evaluate** looks at the full picture. It's deliberately biased toward stopping — it only triggers another iteration when there's a *critical* gap, in which case Strategy updates and Decompose runs again on the new plan.

## [2:35 – 3:00] Wrap

The output is a session folder with the proposal, every task's code and artifacts, the draft history, the reviews, a reproducible Dockerfile, and the polished paper.

One command — `bash start.sh` — runs the whole thing, served at `localhost:8000` with live SSE streaming so you can watch the agents work.

MAARS is open source on GitHub at **dozybot001/MAARS**. Thanks for watching.

---

## Recording Notes

**Pacing**
- ~140 wpm. If you read faster, slow down at the Decompose / Execute / Verify section — those are the dense parts.
- Pause briefly at each section break to let visuals catch up.

**Suggested visuals per section**

| Time | Visual |
|------|--------|
| 0:00–0:20 | Title card → quick montage: typing an idea → paper opening |
| 0:20–0:40 | Pipeline diagram (the Mermaid graph in the README) |
| 0:40–1:00 | Static slide: "Why Research is hard — plan, run, verify, decide" |
| 1:00–1:20 | `calibration.md` and `strategy/round_1.md` opening |
| 1:20–1:40 | `plan_tree.json` rendered as a DAG visualization |
| 1:40–2:10 | Live: parallel task stream + Docker container logs + `artifacts/` populating |
| 2:10–2:35 | Verify verdicts highlighted in the UI; show a redecompose event in the log |
| 2:35–3:00 | Final `paper_polished.md` rendered, then GitHub repo URL |

**Things to emphasize verbally** (the moments where viewers go "oh, that's clever")
1. Refine and Write are the *same* pattern → reduces apparent complexity
2. The persistent-container choice → shows engineering judgment
3. Verify's three-way verdict, especially `redecompose` → not just retry
4. Evaluate biased toward stopping → avoids infinite loops, signals quality awareness

**Things to leave out** (avoid in a 3-minute pitch)
- Rate limiting, deep-copy model isolation, JSON-repair for LaTeX backslashes — interesting but too in-the-weeds for video
- Full env-var table
- GPU setup instructions
