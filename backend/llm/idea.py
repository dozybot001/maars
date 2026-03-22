"""
Idea LLM mode — keywords extraction, literature search, idea refinement.
Full orchestration: Keywords → arXiv/OpenAlex search → Refine.
"""

import json
from typing import Any, Callable, Dict, List, Optional

from loguru import logger

from shared.constants import TEMP_CREATIVE, TEMP_EXTRACT
from llm.client import llm_call, llm_call_structured, load_prompt
from shared.utils import extract_codeblock

# 与 Plan/Task 统一的 on_thinking 签名：(chunk, task_id, operation, schedule_info)
OnThinkingCallback = Callable[[str, Optional[str], Optional[str], Optional[dict]], None]


# LLM 提示词：用于 arXiv 检索，输出英文关键词
_SYSTEM_PROMPT = load_prompt("idea-keywords.txt")


def _parse_keywords_response(text: str) -> List[str]:
    """解析 LLM 返回的 JSON，提取 keywords 列表。失败时抛异常触发 retry。"""
    cleaned = extract_codeblock(text) or (text or "").strip()
    data = json.loads(cleaned)
    keywords = data.get("keywords")
    if not isinstance(keywords, list) or not keywords:
        raise ValueError("keywords must be a non-empty list")
    result = [str(k).strip() for k in keywords if k and str(k).strip()]
    if not result:
        raise ValueError("keywords list contains no valid entries")
    return result[:10]


async def extract_keywords(
    idea: str,
    api_config: dict,
    on_chunk: Optional[OnThinkingCallback] = None,
    abort_event: Optional[Any] = None,
) -> List[str]:
    """从模糊 idea 中提取 arXiv 检索关键词。支持可选流式 on_chunk。"""
    if not idea or not isinstance(idea, str):
        return []
    idea = idea.strip()
    if not idea:
        return []

    def _stream_cb(chunk: str):
        if on_chunk:
            return on_chunk(chunk, None, "Keywords", None)

    try:
        keywords, _raw = await llm_call_structured(
            user=idea,
            api_config=api_config,
            system=_SYSTEM_PROMPT,
            parse_fn=_parse_keywords_response,
            temperatures=[TEMP_EXTRACT, TEMP_EXTRACT],
            on_chunk=_stream_cb if on_chunk else None,
            abort_event=abort_event,
        )
        return keywords
    except Exception:
        return []


# --- Refined Idea 生成 ---

_REFINE_IDEA_SYSTEM_PROMPT = load_prompt("idea-refine.txt")


def _build_papers_context(papers: List[dict], max_chars: int = 4000) -> str:
    """将 papers 转为 prompt 可用的文本，控制长度。"""
    if not papers:
        return "(No papers retrieved)"
    parts = []
    total = 0
    for i, p in enumerate(papers[:15]):
        title = (p.get("title") or "").strip()
        abstract = (p.get("abstract") or "").strip().replace("\n", " ")[:500]
        s = f"[{i + 1}] {title}\n  Abstract: {abstract}\n"
        if total + len(s) > max_chars:
            break
        parts.append(s)
        total += len(s)
    return "\n".join(parts) if parts else "(No papers)"


async def refine_idea_from_papers(
    idea: str,
    papers: List[dict],
    api_config: dict,
    on_chunk: Optional[OnThinkingCallback] = None,
    abort_event: Optional[Any] = None,
) -> str:
    """基于用户 idea 与检索到的 papers，生成可执行的 refined idea。支持可选流式 on_chunk。"""
    idea = (idea or "").strip()
    papers = papers or []

    papers_ctx = _build_papers_context(papers)
    user_content = f"**User's idea:** {idea}\n\n**Retrieved papers:**\n{papers_ctx}\n\n**Output:**"

    def _stream_cb(chunk: str):
        if on_chunk:
            return on_chunk(chunk, None, "Refine", None)

    try:
        response = await llm_call(
            user=user_content,
            api_config=api_config,
            system=_REFINE_IDEA_SYSTEM_PROMPT,
            temperature=TEMP_CREATIVE,
            on_chunk=_stream_cb if on_chunk else None,
            abort_event=abort_event,
        )
        return (response or "").strip()
    except Exception as e:
        logger.warning("Refine idea failed: {}", e)
        return ""


# ── Full orchestration ───────────────────────────────────────────────

async def run_idea_llm(
    idea: str,
    api_config: dict,
    limit: int = 10,
    on_thinking=None,
    abort_event=None,
) -> dict:
    """LLM mode full flow: keywords → search → refine. Returns {keywords, papers, refined_idea}."""
    from agents.idea.literature import search_literature

    cfg = api_config or {}
    keywords = await extract_keywords(idea, cfg, on_chunk=on_thinking, abort_event=abort_event)
    if not keywords:
        keywords = ["research"]

    query = "+".join(str(k).replace(" ", "+") for k in keywords)[:100] or "research"
    source, papers = await search_literature(query, limit=limit, cat=None, source=cfg.get("literatureSource"))
    if not papers:
        raise ValueError(f"No papers retrieved from {source} for query '{query}'.")

    refined = await refine_idea_from_papers(idea, papers, cfg, on_chunk=on_thinking, abort_event=abort_event)
    if on_thinking and not (refined or "").strip():
        refined = await refine_idea_from_papers(idea, papers, cfg, abort_event=abort_event)
    if not (refined or "").strip():
        raise ValueError("Refine stage produced empty refined idea.")

    return {"keywords": keywords, "papers": papers, "refined_idea": refined}
