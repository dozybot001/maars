"""Idea Agent - collect papers and generate refined idea."""

from loguru import logger

from shared.utils import OnThinking

from . import arxiv
from .agent import run_idea_agent
from llm.idea import (
    extract_keywords,
    refine_idea_from_papers,
)
from .literature import search_literature

__all__ = [
    "collect_literature",
    "run_idea_agent",
    "arxiv",
    "extract_keywords",
    "refine_idea_from_papers",
]


async def collect_literature(
    idea: str,
    api_config: dict,
    limit: int = 10,
    on_thinking: OnThinking = None,
    abort_event=None,
) -> dict:
    """
    根据模糊 idea 收集文献并生成可执行 refined idea。

    流程：Keywords（LLM 提取关键词）-> 文献检索（OpenAlex/arXiv）-> Refine（LLM 基于文献生成 refined idea）。

    Args:
        idea: 用户输入的模糊研究想法
        api_config: API 配置
        limit: 返回文献数量上限
        on_thinking: 可选，流式时每收到 LLM token 调用，用于 Thinking 区域展示（Keywords、Refine 两阶段）

    Returns:
        {keywords: [...], papers: [...], refined_idea: "..."}  # refined_idea is Markdown string
    """
    logger.info("Idea collect start idea_chars={} limit={}", len((idea or "").strip()), limit)
    # 1. Keywords：提取检索关键词
    keywords = await extract_keywords(idea, api_config, on_chunk=on_thinking, abort_event=abort_event)
    if not keywords:
        keywords = ["research"]
    logger.info("Idea collect keywords extracted count={} keywords={}", len(keywords), keywords)
    # 2. 文献检索（默认 OpenAlex，可切换 arXiv）
    query = "+".join(str(k).replace(" ", "+") for k in keywords)[:100]
    if not query:
        query = "research"
    source, papers = await search_literature(
        query,
        limit=limit,
        cat=None,
        source=(api_config or {}).get("literatureSource"),
    )
    logger.info("Idea collect search source={} query='{}'", source, query)
    if not papers:
        logger.warning("Idea collect blocked: no papers retrieved for query='{}'", query)
        raise ValueError(
            f"No papers retrieved from {source} for query '{query}'. Refine stage is blocked; please adjust the idea/keywords or retry later."
        )
    logger.info("Idea collect papers retrieved count={} first_title='{}'", len(papers), (papers[0].get("title") or "")[:120])
    # 3. Refine：基于 idea + papers 生成可执行 refined idea
    refined_idea = await refine_idea_from_papers(
        idea, papers, api_config, on_chunk=on_thinking, abort_event=abort_event
    )

    if on_thinking is not None and not (refined_idea or "").strip():
        logger.warning(
            "Idea collect refine returned empty in streaming mode; retrying non-streaming refine query='{}' papers={}",
            query,
            len(papers),
        )
        refined_idea = await refine_idea_from_papers(
            idea,
            papers,
            api_config,
            abort_event=abort_event,
        )

    if not (refined_idea or "").strip():
        logger.warning("Idea collect blocked: refine returned empty output for query='{}' papers={}", query, len(papers))
        raise ValueError("Refine stage produced empty refined idea. Pipeline is blocked to avoid low-quality downstream planning.")

    logger.info("Idea collect complete keywords={} papers={} refined_chars={}", len(keywords), len(papers), len(refined_idea))

    return {"keywords": keywords, "papers": papers, "refined_idea": refined_idea}
