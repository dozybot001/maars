"""
Paper Agent 单轮 LLM 实现 - 大纲生成、分节起草、单轮全文起草。
与 Idea/Plan 对齐：提取可复用的 helper 与 LLM 调用逻辑。
"""

import json
from typing import Any, Callable, Dict, List, Optional

from loguru import logger

from llm.client import llm_call, load_prompt
from shared.utils import build_output_digest, maars_plan_to_paper_format, truncate_text


# ── Helpers ──────────────────────────────────────────────────────────

def synthesize_conclusion_from_outputs(outputs: dict) -> dict:
    """Build conclusion dict from MAARS task outputs for paper draft."""
    findings = []
    for task_id, out in outputs.items():
        if isinstance(out, dict):
            content = out.get("content") or out.get("summary") or str(out)[:500]
            findings.append(f"Task {task_id}: {content}")
        else:
            findings.append(f"Task {task_id}: {str(out)[:500]}")
    return {
        "summary": "Synthesized from task outputs.",
        "key_findings": findings[:10],
        "recommendation": "Review and refine based on full task outputs.",
    }


def format_instruction(format_type: str) -> str:
    if format_type.lower() == "latex":
        return """Output the paper in LaTeX format.
Use standard LaTeX syntax with proper sectioning.
Use \\section{}, \\subsection{}, and academic writing style.
Include placeholders like \\includegraphics{filename.png} where suitable.
"""
    return """Output the paper in Markdown format.
Use markdown headers (#, ##, ###) and academic writing style.
Include placeholders like `[Figure: filename.png]` where suitable.
"""


# ── LLM Calls ────────────────────────────────────────────────────────

async def generate_outline(
    goal: str,
    steps: List[dict],
    output_digest: List[dict],
    api_config: dict,
    abort_event: Optional[Any] = None,
) -> Optional[dict]:
    """Generate a paper outline as JSON. Returns parsed dict or None on failure."""
    system_prompt = load_prompt("paper-outline.txt")
    user_prompt = f"""
Research Goal:
{goal}

Plan Steps:
{json.dumps(steps, ensure_ascii=False, indent=2)}

Task Output Digest:
{json.dumps(output_digest, ensure_ascii=False, indent=2)}
"""
    try:
        raw = await llm_call(
            system=system_prompt,
            user=user_prompt,
            api_config=api_config,
            json_output=True,
            abort_event=abort_event,
        )
        return json.loads(raw)
    except (json.JSONDecodeError, Exception) as e:
        logger.warning("Paper Agent outline JSON parse failed: %s", e)
        return None


async def draft_section(
    *,
    title: str,
    goal: str,
    abstract_focus: str,
    heading: str,
    purpose: str,
    relevant_outputs: List[dict],
    format_type: str,
    api_config: dict,
    abort_event: Optional[Any] = None,
) -> str:
    """Draft a single paper section via LLM."""
    system_prompt = load_prompt("paper-section.txt") + "\n" + format_instruction(format_type)
    user_prompt = f"""
Paper Title: {title}
Paper Goal: {goal}
Abstract Focus: {abstract_focus}
Section Heading: {heading}
Section Purpose: {purpose}
Relevant Task Outputs:
{json.dumps(relevant_outputs, ensure_ascii=False, indent=2)}

Write only this section.
"""
    try:
        resp = await llm_call(
            system=system_prompt,
            user=user_prompt,
            api_config=api_config,
            abort_event=abort_event,
        )
        return resp
    except Exception as e:
        logger.warning("Paper Agent section draft failed: %s", e)
        return f"[Error drafting section '{heading}': {e}]"


async def draft_paper_single_pass(
    *,
    plan: dict,
    outputs: dict,
    api_config: dict,
    format_type: str,
    on_thinking: Optional[Callable[..., Any]] = None,
    abort_event: Optional[Any] = None,
    mock: Optional[str] = None,
) -> str:
    """Single-pass full paper drafting via LLM (non-agent mode)."""
    plan_fmt = maars_plan_to_paper_format(plan)
    conclusion = synthesize_conclusion_from_outputs(outputs or {})
    artifacts = [f"{tid}_output" for tid in (outputs or {}).keys()]

    system_instruction = load_prompt("paper-single-pass.txt") + "\n\n" + format_instruction(format_type)

    user_prompt = f"""
Experiment Title: {plan_fmt.get('title', 'Untitled')}
Goal: {plan_fmt.get('goal', 'N/A')}

Methodology Steps:
{json.dumps(plan_fmt.get('steps', []), ensure_ascii=False, indent=2)}

Conclusion & Findings:
{json.dumps(conclusion, ensure_ascii=False, indent=2)}

Task Output Digest:
{json.dumps(build_output_digest(outputs or {}), ensure_ascii=False, indent=2)}

Available Artifacts (Figures/Tables):
{', '.join(artifacts)}

Please write the full paper.
"""

    async def on_chunk(chunk: str):
        if on_thinking and chunk:
            r = on_thinking(chunk, None, "Paper", None)
            if hasattr(r, "__await__"):
                await r

    result = await llm_call(
        system=system_instruction,
        user=user_prompt,
        api_config=api_config,
        on_chunk=on_chunk,
        abort_event=abort_event,
        mock=mock,
    )
    return result
