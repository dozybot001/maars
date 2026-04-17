# MAARS — 3-Minute Video Script (website walkthrough)

> Delivery: screen-record the live website, scroll through sections as you speak.
> Target: ~3 min / ~420 words at ~140 wpm. Research stage gets the most time.

---

## [0:00 – 0:25] Hero section

Welcome to MAARS — Multi-Agent Automated Research System. The pitch is on the screen: bring a research idea, walk away with a paper. Fully automated, end-to-end.

## [0:25 – 0:55] Pipeline section — Refine & Write

*(scroll to the three stage cards)*

MAARS runs three stages. In **Refine**, an Explorer agent surveys the literature and drafts a proposal; a Critic reviews it. They loop until the critic finds nothing left to fix.

**Write** works the same way — Writer drafts a complete paper from the research outputs, Reviewer critiques, they iterate until zero issues remain. A **Polish** sub-step then does one final LLM pass and appends a deterministic metadata appendix.

## [0:55 – 2:15] Pipeline section — Research

*(stay on the Research stage card)*

The middle stage — **Research** — is where the real work happens.

**Calibrate** runs once: one LLM call that looks at your dataset and sandbox capabilities and defines what an "atomic task" looks like for this specific problem. Then **Strategy** drafts a research plan and a scoring direction.

**Decompose** turns that plan into a dependency DAG — tasks split recursively until each leaf is atomic. Sibling judges run in parallel, so one bad branch doesn't stall the whole tree.

**Execute** runs those tasks in parallel, respecting dependency order. Key design decision: instead of spinning up a fresh container per task, MAARS keeps **one persistent Docker container** alive for the whole session, reusing it via `exec_run`. That eliminates roughly 190 seconds of package-install overhead per task.

Every task then goes through **Verify** — three possible verdicts: pass, retry, or **redecompose**. Redecompose splits a failed task into subtasks and passes prior partial outputs as context, so the system refines rather than restarts from scratch.

Finally, **Evaluate** looks at the full picture. It's deliberately biased toward stopping — it only triggers another iteration when there's a critical gap in the results.

## [2:15 – 2:35] Showcase section

*(scroll to showcase)*

The outputs are real. Here MAARS worked on a CIFAR image classification problem — real training curves, real accuracy numbers, real generated figures. Everything in the paper came from actual code execution inside the sandbox.

## [2:35 – 2:45] Docs section

*(scroll to docs)*

If you want to go deeper, the website has full documentation covering the five-layer architecture, the agent loop design in Refine and Write, and the Research stage internals — Calibrate through Evaluate — in detail.

## [2:45 – 3:00] Quickstart + CTA

*(scroll to quickstart)*

Getting started is one command: `bash start.sh`. It sets up the environment, builds the Docker image, and opens the server at localhost:8000.

MAARS is open source on GitHub at **dozybot001/MAARS**. Thanks for watching.

---

## Recording notes

| Time | Screen |
|------|--------|
| 0:00–0:25 | Hero — let the tagline sit for a beat before speaking |
| 0:25–0:55 | Pipeline — scroll slowly across the three stage cards |
| 0:55–2:15 | Stay on the Research card; point to each phase label as you name it |
| 2:15–2:35 | Showcase — hover over the CIFAR charts |
| 2:35–2:45 | Docs section — scroll past the three doc cards |
| 2:45–3:00 | Quickstart section, end on the GitHub CTA |

**Pacing tip:** the Research block (0:55–2:15) is 80 seconds for 6 phases — roughly 12 seconds per phase. Don't rush; let each name land before moving on.
