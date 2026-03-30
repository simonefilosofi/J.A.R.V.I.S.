#!/usr/bin/env python3
"""
JARVIS Web Search Tool — powered by Tavily.
Get a free API key at https://app.tavily.com (1000 req/month free tier).
"""

import json
import os

try:
    from tavily import TavilyClient as _TavilyClient
    _client = _TavilyClient(api_key=os.environ.get("TAVILY_API_KEY", "")) \
              if os.environ.get("TAVILY_API_KEY") else None
except ImportError:
    _client = None

# ── Tool definition for Groq function calling ─────────────────
TOOL_DEF = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": (
            "Search the internet for up-to-date information. Use this whenever the user asks "
            "about current events, news, prices, weather in specific cities, sports results, "
            "recent releases, or any topic that may have changed after your training cutoff."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query in the most effective form for a web search engine."
                }
            },
            "required": ["query"]
        }
    }
}


_NEWS_KEYWORDS = ("notizie", "news", "oggi", "ultimo", "recente", "ultime", "latest", "current", "recent")

def web_search(query: str, topic: str = None) -> dict:
    if not _client:
        return {
            "ok": False,
            "error": "TAVILY_API_KEY not configured. Add it to your .env file (free key at app.tavily.com)."
        }
    if topic not in ("general", "news"):
        topic = "news" if any(k in query.lower() for k in _NEWS_KEYWORDS) else "general"
    try:
        response = _client.search(
            query=query,
            search_depth="advanced",
            topic=topic,
            max_results=5,
            include_answer="advanced",
        )

        # Build a compact but rich summary for the LLM
        lines = []

        if response.get("answer"):
            lines.append(f"SUMMARY: {response['answer']}\n")

        for i, r in enumerate(response.get("results", []), 1):
            title   = r.get("title", "")
            url     = r.get("url", "")
            content = r.get("content", "").strip()
            # Trim very long snippets
            if len(content) > 400:
                content = content[:400] + "…"
            lines.append(f"[{i}] {title}\n{url}\n{content}")

        if not lines:
            return {"ok": False, "error": "No results found."}

        return {"ok": True, "result": "\n\n".join(lines)}

    except Exception as e:
        return {"ok": False, "error": str(e)[:120]}


def dispatch_tool_call(tool_name: str, arguments) -> str:
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except Exception:
            return "Error: could not parse tool arguments."

    if tool_name == "web_search":
        result = web_search(query=arguments.get("query", ""))
        return result["result"] if result["ok"] else f"Search error: {result['error']}"

    return f"Unknown tool: {tool_name}"
