"""Academic search tools — arXiv and Semantic Scholar APIs."""

import httpx


def create_academic_tools() -> list:
    """Create academic search tools. No API key needed."""
    return [arxiv_search, semantic_scholar_search]


async def arxiv_search(query: str, max_results: int = 5) -> str:
    """Search arXiv for papers matching a query.
    Returns titles, authors, abstracts, and arXiv IDs.
    Use this to find real papers and ground your research in actual literature."""
    url = "https://export.arxiv.org/api/query"
    params = {
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": min(max_results, 10),
        "sortBy": "relevance",
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
    except Exception as e:
        return f"arXiv search failed: {e}"

    return _parse_arxiv_response(resp.text)


async def semantic_scholar_search(query: str, max_results: int = 5) -> str:
    """Search Semantic Scholar for papers, citations, and influence metrics.
    Returns titles, authors, citation counts, and abstracts.
    Use this to assess paper impact and find citation relationships."""
    url = "https://api.semanticscholar.org/graph/v1/paper/search"
    params = {
        "query": query,
        "limit": min(max_results, 10),
        "fields": "title,authors,abstract,citationCount,year,externalIds",
    }
    headers = {"User-Agent": "MAARS/1.0 (research pipeline)"}
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        return f"Semantic Scholar search failed: {e}"

    papers = data.get("data", [])
    if not papers:
        return f"No results found for: {query}"

    results = []
    for p in papers:
        authors = ", ".join(a.get("name", "") for a in (p.get("authors") or [])[:3])
        if len(p.get("authors") or []) > 3:
            authors += " et al."
        arxiv_id = (p.get("externalIds") or {}).get("ArXiv", "")
        results.append(
            f"**{p.get('title', 'Untitled')}**\n"
            f"  Authors: {authors}\n"
            f"  Year: {p.get('year', '?')} | Citations: {p.get('citationCount', '?')}"
            + (f" | arXiv: {arxiv_id}" if arxiv_id else "") +
            f"\n  Abstract: {(p.get('abstract') or 'N/A')[:200]}..."
        )

    return "\n\n".join(results)


def _parse_arxiv_response(xml_text: str) -> str:
    """Simple XML parsing for arXiv Atom feed — no lxml dependency."""
    import re

    entries = re.findall(r"<entry>(.*?)</entry>", xml_text, re.DOTALL)
    if not entries:
        return "No results found."

    results = []
    for entry in entries:
        title = _extract_tag(entry, "title").strip().replace("\n", " ")
        summary = _extract_tag(entry, "summary").strip().replace("\n", " ")[:200]
        arxiv_id = _extract_tag(entry, "id").split("/abs/")[-1] if "/abs/" in _extract_tag(entry, "id") else ""
        authors = re.findall(r"<name>(.*?)</name>", entry)
        author_str = ", ".join(authors[:3])
        if len(authors) > 3:
            author_str += " et al."

        results.append(
            f"**{title}**\n"
            f"  Authors: {author_str}\n"
            f"  arXiv: {arxiv_id}\n"
            f"  Abstract: {summary}..."
        )

    return "\n\n".join(results)


def _extract_tag(text: str, tag: str) -> str:
    import re
    match = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", text, re.DOTALL)
    return match.group(1) if match else ""
