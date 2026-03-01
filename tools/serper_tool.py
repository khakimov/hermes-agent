"""
Serper Google Search tool.

Uses the Serper.dev API for Google search results.
Requires SERPER_API_KEY environment variable.
"""

import json
import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

SERPER_API_URL = "https://google.serper.dev/search"

# Valid time range filters (Serper "tbs" parameter)
_TIME_RANGES = {
    "hour": "qdr:h",
    "day": "qdr:d",
    "week": "qdr:w",
    "month": "qdr:m",
    "year": "qdr:y",
}


def check_serper_api_key() -> bool:
    return bool(os.getenv("SERPER_API_KEY"))


def serper_search_tool(
    query: str,
    time_range: Optional[str] = None,
    page: int = 1,
) -> str:
    """Search Google via Serper API."""
    api_key = os.getenv("SERPER_API_KEY")
    if not api_key:
        return json.dumps({"error": "SERPER_API_KEY not set"})

    if not query or not query.strip():
        return json.dumps({"error": "query is required"})

    payload = {"q": query.strip(), "page": max(1, page)}

    if time_range:
        tbs = _TIME_RANGES.get(time_range.lower())
        if tbs:
            payload["tbs"] = tbs

    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json",
    }

    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(SERPER_API_URL, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        return json.dumps({"error": f"Serper API request failed: {e}"})

    # Format results
    results = []

    # Knowledge graph (if present)
    kg = data.get("knowledgeGraph")
    if kg:
        results.append({
            "type": "knowledge_graph",
            "title": kg.get("title", ""),
            "description": kg.get("description", ""),
            "attributes": kg.get("attributes", {}),
        })

    # Organic results
    for item in data.get("organic", []):
        results.append({
            "type": "organic",
            "title": item.get("title", ""),
            "url": item.get("link", ""),
            "snippet": item.get("snippet", ""),
            "position": item.get("position"),
        })

    # "People also ask"
    for item in data.get("peopleAlsoAsk", []):
        results.append({
            "type": "people_also_ask",
            "question": item.get("question", ""),
            "snippet": item.get("snippet", ""),
            "url": item.get("link", ""),
        })

    return json.dumps({
        "query": query,
        "page": page,
        "time_range": time_range,
        "num_results": len(results),
        "results": results,
    }, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
from tools.registry import registry

SERPER_SEARCH_SCHEMA = {
    "name": "serper_search",
    "description": (
        "Search Google via Serper API. Returns organic results, knowledge graph, "
        "and 'people also ask'. Supports pagination and time filtering."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query",
            },
            "time_range": {
                "type": "string",
                "enum": ["hour", "day", "week", "month", "year"],
                "description": "Filter results by recency (optional)",
            },
            "page": {
                "type": "integer",
                "description": "Results page number (default 1)",
                "default": 1,
            },
        },
        "required": ["query"],
    },
}

registry.register(
    name="serper_search",
    toolset="web",
    schema=SERPER_SEARCH_SCHEMA,
    handler=lambda args, **kw: serper_search_tool(
        query=args.get("query", ""),
        time_range=args.get("time_range"),
        page=args.get("page", 1),
    ),
    check_fn=check_serper_api_key,
    requires_env=["SERPER_API_KEY"],
)
