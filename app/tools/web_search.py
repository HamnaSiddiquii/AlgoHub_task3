"""
Web search tool.

Uses duckduckgo-search style backends (no API key needed) so this repo
runs out-of-the-box. As of mid-2025 the original `duckduckgo-search`
package was frozen and renamed to `ddgs` (same API: DDGS().text(...)).
We prefer the new package and fall back to the old one so this works
regardless of which one ended up installed.

If you'd rather use a paid provider (Tavily, SerpAPI, Bing), swap the
body of `search_web` for that client's call — the Tool interface below
doesn't need to change.
"""

from langchain_core.tools import Tool

try:
    from ddgs import DDGS  # actively maintained package (new name)
except ImportError:
    try:
        from duckduckgo_search import DDGS  # legacy package (frozen, may still work)
    except ImportError:
        DDGS = None

MAX_RESULTS = 5


def search_web(query: str) -> str:
    """Search the web and return a short list of titles/snippets/links."""
    if DDGS is None:
        return (
            "WebSearchError: no search backend is installed. "
            "Run: pip install ddgs   (or: pip install duckduckgo-search)"
        )
    if not query or not query.strip():
        return "WebSearchError: empty query"

    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=MAX_RESULTS))
        if not results:
            return f"No results found for: {query}"

        lines = []
        for i, r in enumerate(results, 1):
            title = r.get("title", "").strip()
            body = r.get("body", "").strip()
            href = r.get("href", "").strip()
            lines.append(f"{i}. {title}\n   {body}\n   {href}")
        return "\n".join(lines)
    except Exception as e:  # noqa: BLE001
        return f"WebSearchError: search failed ({e})"


web_search_tool = Tool(
    name="web_search",
    func=search_web,
    description=(
        "Searches the public web for current information (news, facts, docs) and returns "
        "the top results with titles, snippets, and links. Input is a plain-text search query. "
        "Use this when the answer likely depends on information newer than the model's training "
        "data, or when you need a citable source."
    ),
)