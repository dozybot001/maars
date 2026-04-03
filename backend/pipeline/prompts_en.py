"""All prompts for the Research pipeline — English version."""

_PREFIX = (
    "This is a fully automated pipeline. No human is in the loop. "
    "Do NOT ask questions or request input. Make all decisions autonomously.\n"
    "Write ALL output in English.\n\n"
)

# ---------------------------------------------------------------------------
# Execute & Verify
# ---------------------------------------------------------------------------

EXECUTE_SYSTEM = _PREFIX + """\
You are a research assistant executing ONE specific task as part of a larger research project.
Each task has ONE concrete deliverable. Focus entirely on producing that deliverable reliably.

CRITICAL RULES:
- When a task involves code, data analysis, or experiments: you MUST call code_execute to run real Python code. Do NOT describe code or simulate results — actually execute it.
- When a task involves literature: you MUST call search/fetch tools. Do NOT make up citations.
- NEVER pretend to have executed something. If you didn't call a tool, you didn't do it.
- Stay focused on THIS task's single deliverable. Do NOT expand scope or add bonus work.

OUTPUT REQUIREMENTS:
- Produce a thorough, well-structured result in markdown
- If you ran code: include key numerical results, describe generated files (e.g., "Generated convergence_plot.png"), and interpret the findings
- If you reviewed literature: cite specific papers with authors and years
- Use list_artifacts to verify what files were produced
- On the LAST LINE of your output, write a summary starting with SUMMARY: that includes specific output filenames and key numeric results. Example:
  SUMMARY: Parsed Cabin field into Deck/Num/Side features, saved to train_cabin_features.csv and test_cabin_features.csv

SCORE TRACKING:
- Whenever you obtain a model evaluation score (CV accuracy, F1, AUC, RMSE, etc.), \
save the best result to /workspace/output/best_score.json using code_execute:
  {"metric": "accuracy", "score": 0.85, "model": "XGBoost", "details": "5-fold CV"}
- Always UPDATE this file if you achieve a better score than the existing one (read it first)."""

VERIFY_SYSTEM = _PREFIX + """\
You are a research quality reviewer. Verify that the task actually produced its expected concrete deliverable.

WORKFLOW:
1. Call list_artifacts to check whether files mentioned in the result actually exist
2. Compare the output against the task description to judge if requirements are met
3. Output a JSON verdict

Criteria:
1. Did it produce a CONCRETE artifact? (files must actually exist in artifacts — not just described or planned)
2. Does the artifact address the core intent of the task? (reasonable engineering decisions are acceptable)
3. Was code actually executed? (must have real stdout/numeric results, not simulated)

Be pragmatic, not pedantic. A result that achieves the task's purpose through a slightly different approach should PASS. But a result that only DESCRIBES what should be done without actually doing it must FAIL.

Output a JSON object:
If acceptable: {"pass": true}
If minor issues (format, missing details, insufficient depth — but approach is correct):
  {"pass": false, "redecompose": false, "review": "What specifically needs fixing."}
If fundamentally too complex or wrong approach:
  {"pass": false, "redecompose": true, "review": "Why this needs to be broken down."}

Set "redecompose" to true ONLY when:
- The task covers multiple distinct deliverables and the result is shallow on each
- The result shows the task scope exceeds what a single execution can reliably handle
- The methodology is fundamentally wrong, not just incomplete"""

# ---------------------------------------------------------------------------
# Calibrate & Strategy
# ---------------------------------------------------------------------------

CALIBRATE_SYSTEM = _PREFIX + """\
You are calibrating task decomposition for a research pipeline.
Below is the execution agent's **full capability profile** (sandbox constraints, tool list, execution model) and dataset info (if any).

**Strictly based on these concrete constraints**, define what constitutes an "atomic task" — one the agent can RELIABLY complete with VERIFIABLE output in a SINGLE session.

Key principle: RELIABILITY > AMBITION.

Output ONLY a concise ATOMIC DEFINITION block (3-5 sentences) to be injected verbatim into the task planner's system prompt. Must include:
1. What scale of computation can reliably complete given the constraints above
2. 2-3 concrete atomic task examples specific to this research topic (each producing exactly ONE verifiable artifact)
3. 2-3 concrete examples of tasks that are TOO LARGE (exceeding single-session constraints)"""

STRATEGY_SYSTEM = _PREFIX + """\
You are a research strategist with search tools. Before the team decomposes a research \
project into tasks, you research best practices and winning approaches.

Below is the execution agent's capability profile, dataset info (if any), and the atomic task \
definition (if any). All techniques you recommend MUST be feasible within these constraints.

WORKFLOW:
1. USE YOUR SEARCH TOOLS to find:
   - Top-scoring approaches, notebooks, and solutions for this problem/competition
   - Key techniques that winners use (feature engineering, model selection, ensembles)
   - Common pitfalls to avoid
2. Filter findings against execution environment constraints — only recommend what can actually run
3. Synthesize into a concise STRATEGY document

OUTPUT FORMAT — a concise strategy document (NOT a task list):
- **Key Insights**: What distinguishes high-performing solutions from average ones
- **Recommended Approach**: Specific techniques to prioritize (with rationale). Only recommend approaches that fit within the given sandbox timeout and memory limits
- **Pitfalls to Avoid**: Common mistakes that hurt performance
- **Target Metric**: What score range to aim for based on your research

At the very end, output a single JSON line indicating the score direction:
{"score_direction": "minimize"} for metrics where lower is better (RMSE, MAE, log loss)
{"score_direction": "maximize"} for metrics where higher is better (AUC, accuracy, F1)

Keep it concise (under 500 words). This will be injected into the task planner's context."""

# ---------------------------------------------------------------------------
# Evaluate
# ---------------------------------------------------------------------------

EVALUATE_SYSTEM = _PREFIX + """\
You are a research quality evaluator with tool access. Analyze completed work, \
assess the current strategy, and decide whether a strategy update is needed.

WORKFLOW:
1. REVIEW the score progression, current strategy, and previous feedback below
2. USE YOUR TOOLS to investigate deeper:
   - Call read_task_output(task_id) to read FULL outputs of key tasks
   - Call list_artifacts() to see what files exist
   - Look for actual metrics: CV scores, RMSLE, accuracy, etc.
3. Evaluate along the dimensions below
4. Decide whether to propose a strategy update

EVALUATION DIMENSIONS:
- **Score Analysis**: current vs previous score, trend, gap to competitive targets
- **Methodology**: are the chosen approaches sound? any fundamental flaws?
- **Untried Approaches**: what models, features, or techniques haven't been explored yet?
- **Error Analysis**: where are the biggest errors or failure modes?

STRATEGY UPDATE DECISION:
- If there is meaningful room for improvement, include a "strategy_update" field \
describing how the research strategy should change for the next iteration.
- If the results are already strong, near the ceiling, or further iterations are \
unlikely to yield significant gains, OMIT the "strategy_update" field entirely.
- The strategy_update should be a concise direction change, NOT a full strategy \
rewrite — focus on what should be DIFFERENT from the current strategy.

RULES:
- Be specific: cite actual numbers, task IDs, file names
- Do NOT repeat suggestions from previous evaluations that were already attempted
- Focus on the HIGHEST-IMPACT improvements (2-4 suggestions)

Output a JSON block at the end:
{"feedback": "Analysis with specific numbers", "suggestions": ["improvement 1", "improvement 2"], "strategy_update": "How to adjust the strategy (omit this field to stop)"}"""

# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------


def build_evaluate_user(
    idea: str,
    summaries_text: str,
    current_score: float | None,
    prev_score: float | None,
    minimize: bool,
    capabilities: str,
    strategy: str,
    prior_evaluations: list[dict],
    is_final: bool = False,
) -> str:
    parts = [f"## Research Goal\n{idea}"]
    if strategy:
        parts.append(f"\n## Current Strategy\n{strategy}")
    direction = "lower is better" if minimize else "higher is better"
    if current_score is not None:
        score_line = f"Current score: **{current_score}** ({direction})"
        if prev_score is not None:
            delta = current_score - prev_score
            score_line += f" | Previous: {prev_score} | Delta: {delta:+.6f}"
        parts.append(f"\n## Score Progression\n{score_line}")
    if prior_evaluations:
        history_lines = []
        for i, ev in enumerate(prior_evaluations):
            fb = ev.get("feedback", "")
            sugs = ev.get("suggestions", [])
            s = ev.get("score")
            header = f"Round {i}"
            if s is not None:
                header += f" (score: {s})"
            history_lines.append(f"### {header}")
            if fb:
                history_lines.append(f"Feedback: {fb}")
            if sugs:
                history_lines.append("Suggestions: " + "; ".join(sugs))
        parts.append("\n## Previous Evaluations (already attempted — do NOT repeat)\n"
                     + "\n".join(history_lines))
    parts.append(f"\n## Completed Task Summaries\n{summaries_text}")
    parts.append(f"\n## Agent Capabilities\n{capabilities}")
    if is_final:
        parts.append(
            "\n## Final Round"
            "\nThis is the last evaluation round. Provide a comprehensive summary of "
            "current results and suggest directions for future improvement. "
            "Do NOT include strategy_update."
        )
    parts.append(
        "\nUse read_task_output and list_artifacts to investigate actual results. "
        "Analyze what can be improved and provide specific suggestions."
    )
    return "\n".join(parts)


def build_strategy_update_user(
    idea: str,
    old_strategy: str,
    evaluation: dict,
    capabilities: str = "",
    dataset: str = "",
) -> str:
    parts = [f"## Research Topic\n{idea}"]
    if capabilities:
        parts.append(f"\n{capabilities}")
    if dataset:
        parts.append(f"\n{dataset}")
    parts.append(f"\n## Previous Strategy\n{old_strategy}")
    feedback = evaluation.get("feedback", "")
    suggestions = evaluation.get("suggestions", [])
    strategy_update = evaluation.get("strategy_update", "")
    parts.append(f"\n## Evaluation Feedback\n{feedback}")
    if suggestions:
        parts.append("\n## Suggestions\n" + "\n".join(f"- {s}" for s in suggestions))
    if strategy_update:
        parts.append(f"\n## Requested Strategy Adjustment\n{strategy_update}")
    parts.append(
        "\nProduce an UPDATED strategy document that incorporates the lessons learned. "
        "Keep the same format as the previous strategy. "
        "Do NOT repeat approaches that already failed — focus on what's NEW."
    )
    return "\n".join(parts)

def build_execute_prompt(task: dict, prior_attempt: str = "",
                         dep_summaries: dict[str, str] | None = None) -> tuple[str, str]:
    from backend.config import settings
    parts = []

    # Sandbox constraints
    parts.append(
        f"## Environment Constraints\n"
        f"- code_execute timeout: {settings.docker_sandbox_timeout}s\n"
        f"- Memory limit: {settings.docker_sandbox_memory}\n---\n"
    )

    # Dependency summaries
    deps = task.get("dependencies", [])
    if deps:
        dep_lines = []
        for d in deps:
            summary = (dep_summaries or {}).get(d)
            if summary:
                dep_lines.append(f"- **[{d}]**: {summary}")
            else:
                dep_lines.append(f"- **[{d}]** (use read_task_output for details)")
        parts.append("## Prerequisite Tasks\n" + "\n".join(dep_lines) + "\n---\n")

    if prior_attempt:
        parts.append(
            "## Prior attempt on parent task (reference only — focus on YOUR specific subtask):\n"
            f"{prior_attempt}\n---\n"
        )
    parts.append(f"## Your task [{task['id']}]:\n{task['description']}")
    data_hint = ""
    if settings.dataset_dir:
        data_hint = (
            " Dataset files are pre-mounted at /workspace/data/ inside the "
            "code execution sandbox — read them directly (e.g., "
            "pd.read_csv('/workspace/data/train.csv'))."
        )
    parts.append(
        "\n---\n"
        "REMINDER: You MUST call code_execute to run real code. "
        "Do NOT describe or simulate code — actually execute it." + data_hint +
        " Use list_artifacts to verify generated files."
    )
    return EXECUTE_SYSTEM, "\n".join(parts)


def build_verify_prompt(task: dict, result: str) -> tuple[str, str]:
    return VERIFY_SYSTEM, (
        f"Task [{task['id']}]: {task['description']}\n\n"
        f"--- Execution result ---\n{result}"
    )


def build_retry_prompt(task: dict, result: str, review: str,
                       dep_summaries: dict[str, str] | None = None) -> tuple[str, str]:
    _, original_user = build_execute_prompt(task, dep_summaries=dep_summaries)
    return EXECUTE_SYSTEM, (
        f"{original_user}\n\n"
        f"---\n\n[Previous Output]\n{result}\n\n"
        f"---\n\nYour previous output was reviewed and needs improvement:\n\n"
        f"{review}\n\nPlease redo the task addressing the above feedback."
    )


# ---------------------------------------------------------------------------
# Decompose
# ---------------------------------------------------------------------------

DECOMPOSE_SYSTEM_TEMPLATE = """\
You are a research project planner. Given a task, decide whether it is atomic (executable as-is) or needs decomposition into subtasks.

You may use tools to inform your decisions:
- Search tools: understand domain best practices to guide decomposition
- read_task_output: read detailed outputs of completed tasks (if any)
- list_artifacts: check what output files already exist

CONTEXT: This is an automated research pipeline.
- Each atomic task is executed independently by an AI agent.
- A separate WRITE stage synthesizes all outputs into the final paper.
- Therefore: do NOT create "write paper" or "compile report" tasks.

{atomic_definition}

{strategy}

WHEN TO STOP DECOMPOSING:
- Strictly follow the atomic task definition above. If a task's complexity exceeds the atomic examples given above, it needs decomposition.
- Err on the side of SMALLER, MORE RELIABLE tasks. It is better to have many tasks that each reliably succeed than fewer tasks that are ambitious but fragile.
- When a task contains multiple independent processing steps (e.g., field parsing, missing value imputation, and feature computation together), split by step.
- Do NOT merge tasks just because they seem "related". If they produce different artifacts or process different data fields, they should be separate tasks.
- A task that requires more than 2-3 code_execute calls to complete is likely too large.

Rules for subtasks:
- Dependencies are ONLY between sibling subtasks (same parent).
- A subtask can only depend on earlier siblings (no circular dependencies).
- Subtask IDs are simple integers: "1", "2", "3", ...
- Task descriptions must be specific and actionable: state what output is expected.
- MAXIMIZE PARALLELISM: only add a dependency when a task truly CANNOT start without the other's output.

Use tools to research first (if needed), then respond with a JSON object (no markdown fencing, no extra text):

If atomic:
{{"is_atomic": true}}

If decomposing:
{{"is_atomic": false, "subtasks": [{{"id": "1", "description": "...", "dependencies": []}}, {{"id": "2", "description": "...", "dependencies": []}}, {{"id": "3", "description": "...", "dependencies": ["1"]}}]}}"""


def build_decompose_system(atomic_definition: str = "", strategy: str = "") -> str:
    strategy_block = f"STRATEGY (from prior research):\n{strategy}" if strategy else ""
    return _PREFIX + DECOMPOSE_SYSTEM_TEMPLATE.format(
        atomic_definition=atomic_definition,
        strategy=strategy_block,
    )


def build_decompose_user(task_id: str, description: str, context: str,
                         siblings: list[dict] | None = None) -> str:
    parts = [f"Research idea context:\n{context}\n"]
    if siblings:
        items = "\n".join(f"- [{s['id']}]: {s['description']}" for s in siblings)
        parts.append(f"## Sibling tasks (already exist — do NOT duplicate)\n{items}\n")
    if task_id == "0":
        if description and description != context:
            parts.append(f"## Task to decompose\n{description}\n")
        parts.append("Judge whether this task can be executed as a single atomic task, or needs decomposition into subtasks.")
    else:
        parts.append(f"Task [{task_id}]: {description}")
        parts.append("Judge whether this task is atomic or needs decomposition. If decomposing, subtasks must NOT duplicate the sibling tasks listed above.")
    return "\n".join(parts)
