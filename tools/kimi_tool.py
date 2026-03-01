#!/usr/bin/env python3
"""Kimi Tool

First-class Hermes tool for calling the Kimi Coding API (Anthropic-compatible messages endpoint).

Environment variables (recommended: set in ~/.hermes/.env):
- KIMI_API_KEY (required)
- KIMI_URL (default: https://api.kimi.com/coding/v1/messages)
- KIMI_MODEL (default: kimi-k2.5)
- KIMI_MAX_TOKENS (default: 4096)
- KIMI_TIMEOUT (default: 300 seconds)

Tool name: `kimi`

Returns:
- JSON string: {"text": "...", "model": "..."}
- On error: {"error": "..."}
"""

import json
import os
import logging
from typing import Any, Dict, Optional

import requests

from tools.registry import registry

logger = logging.getLogger(__name__)


def check_kimi_api_key() -> bool:
    """Return True if Kimi is configured."""
    return bool(os.getenv("KIMI_API_KEY"))


def _env_int(name: str, default: int) -> int:
    val = os.getenv(name)
    if val is None or val == "":
        return default
    try:
        return int(val)
    except Exception:
        return default


def _call_kimi(
    prompt: str,
    model: Optional[str] = None,
    max_tokens: Optional[int] = None,
    timeout: Optional[int] = None,
) -> Dict[str, Any]:
    api_key = os.getenv("KIMI_API_KEY")
    if not api_key:
        return {"error": "KIMI_API_KEY not configured"}

    url = os.getenv("KIMI_URL", "https://api.kimi.com/coding/v1/messages")
    model = model or os.getenv("KIMI_MODEL", "kimi-k2.5")
    max_tokens = max_tokens if max_tokens is not None else _env_int("KIMI_MAX_TOKENS", 4096)
    timeout = timeout if timeout is not None else _env_int("KIMI_TIMEOUT", 300)

    payload = {
        "model": model,
        "max_tokens": int(max_tokens),
        "messages": [{"role": "user", "content": prompt}],
    }

    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
        # Try to parse JSON even on non-200 to surface useful errors.
        try:
            data = resp.json()
        except Exception:
            data = None

        if resp.status_code >= 400:
            if isinstance(data, dict):
                # Anthropic-style error
                if "error" in data:
                    err = data.get("error")
                    if isinstance(err, dict):
                        return {"error": err.get("message") or json.dumps(err)}
                    return {"error": str(err)}
                if "message" in data:
                    return {"error": str(data.get("message"))}
            return {"error": f"HTTP {resp.status_code}: {resp.text[:500]}"}

        if isinstance(data, dict) and "content" in data and data["content"]:
            # Anthropic messages: content is a list of blocks
            block0 = data["content"][0]
            if isinstance(block0, dict) and "text" in block0:
                return {"text": block0["text"], "model": model}

        # Fallback
        if data is not None:
            return {"text": json.dumps(data), "model": model}
        return {"error": "Unexpected response (non-JSON)"}

    except Exception as e:
        logger.exception("Kimi tool call failed")
        return {"error": str(e)}


KIMI_SCHEMA = {
    "name": "kimi",
    "description": "Query Kimi Coding API (Anthropic-compatible). Returns {text, model}.",
    "parameters": {
        "type": "object",
        "properties": {
            "prompt": {"type": "string", "description": "User prompt to send to Kimi"},
            "model": {"type": "string", "description": "Model name (default from env KIMI_MODEL)"},
            "max_tokens": {"type": "integer", "description": "Max tokens (default from env KIMI_MAX_TOKENS)", "default": 4096},
            "timeout": {"type": "integer", "description": "Timeout in seconds (default from env KIMI_TIMEOUT)", "default": 300},
        },
        "required": ["prompt"],
    },
}


registry.register(
    name="kimi",
    toolset="kimi",
    schema=KIMI_SCHEMA,
    handler=lambda args, **kw: json.dumps(
        _call_kimi(
            prompt=args.get("prompt", ""),
            model=args.get("model"),
            max_tokens=args.get("max_tokens"),
            timeout=args.get("timeout"),
        )
    ),
    check_fn=check_kimi_api_key,
    requires_env=["KIMI_API_KEY"],
)
