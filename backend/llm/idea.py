"""
Idea Agent 单轮 LLM 实现 - 关键词提取 + Refined Idea 生成。
与 Plan 对齐：Mock 模式依赖 test/mock-ai/refine.json、refine-idea.json。
Refine 流程：Keywords（关键词提取）→ arXiv 检索 → Refine（基于文献生成可执行 idea）。
"""

import json
from typing import Any, Callable, Dict, List, Optional

from loguru import logger

from shared.constants import TEMP_CREATIVE, TEMP_EXTRACT
from llm.client import llm_call, llm_call_structured, load_prompt
from mock import load_mock
from shared.utils import extract_codeblock

# 与 Plan/Task 统一的 on_thinking 签名：(chunk, task_id, operation, schedule_info)
OnThinkingCallback = Callable[[str, Optional[str], Optional[str], Optional[dict]], None]

RESPONSE_TYPE_KEYWORDS = "refine"
RESPONSE_TYPE_REFINE = "refine-idea"


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

    mock = None
    if api_config.get("ideaUseMock", True):
        entry = load_mock(RESPONSE_TYPE_KEYWORDS)
        if not entry:
            raise ValueError(f"No mock data for {RESPONSE_TYPE_KEYWORDS}/_default")
        mock = entry["content"]

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
            mock=mock,
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

    mock = None
    if api_config.get("ideaUseMock", True):
        entry = load_mock(RESPONSE_TYPE_REFINE)
        mock = entry["content"] if entry else None

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
            mock=mock,
        )
        return (response or "").strip()
    except Exception as e:
        logger.warning("Refine idea failed: {}", e)
        return ""
