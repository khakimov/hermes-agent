#!/usr/bin/env python3
"""
Reload Tools Module - Dynamic Tool Loading at Runtime

Provides a meta-tool that safely loads new tool modules into the live registry.
Designed to be the final step of a safety pipeline:

  1. write_file("tools/my_tool.py", code)
  2. terminal("python -c \"import importlib; importlib.import_module('tools.my_tool')\"")
     → validates syntax/imports/register() in a subprocess (crash-safe)
  3. terminal("python -c \"from tools.my_tool import ...; print(handler({...}))\"")
     → validates handler returns valid JSON in a subprocess
  4. reload_tools(module_name="tools.my_tool")   ← THIS TOOL (in-process)

Steps 2-3 run in subprocesses — if they crash, the gateway is unaffected.
Only step 4 touches the live process, and by then the module is validated.
"""

import importlib
import json
import os
import re
import sys
import logging
from typing import Dict, Any, Set

from tools.registry import registry

logger = logging.getLogger(__name__)

# Capture built-in tool names at import time (before any dynamic loading).
# This is a frozen snapshot — used to prevent dynamic tools from overwriting
# core tools that shipped with hermes-agent.
_BUILTIN_TOOL_NAMES = frozenset(registry.get_all_tool_names())

# Track which module registered which tools and under which toolset —
# enables accurate reload detection, cross-module ownership checks,
# and proper cleanup when a module removes tools or changes toolset.
_MODULE_TOOL_MAP: Dict[str, dict] = {}  # {module: {"tools": set, "toolset": str}}

# Internal modules that must never be reloaded via this tool.
_PROTECTED_MODULES = frozenset({
    "tools.registry",
    "tools.__init__",
    "tools.reload_tools",
})


def _validate_module_name(module_name: str) -> str | None:
    """Validate module_name format. Returns error string or None if valid."""
    if not module_name or not isinstance(module_name, str):
        return "module_name is required and must be a string"

    parts = module_name.split(".")
    if len(parts) != 2 or parts[0] != "tools":
        return (
            f"module_name must be 'tools.<name>' (exactly 2 parts), "
            f"got '{module_name}'"
        )

    name_part = parts[1]
    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", name_part):
        return f"Invalid module name component: '{name_part}'"

    if module_name in _PROTECTED_MODULES:
        return f"Cannot reload protected module: '{module_name}'"

    return None


def reload_tools_handler(args: Dict[str, Any], **kwargs) -> str:
    """
    Load or reload a tool module into the live registry.

    This runs importlib.import_module() (or reload()) in the current process.
    The module's top-level registry.register() calls execute immediately,
    making new tools available on the next agent turn.
    """
    module_name = args.get("module_name", "")
    toolset = args.get("toolset", "dynamic")
    add_to_all_platforms = args.get("add_to_all_platforms", True)

    # --- Validation ---
    err = _validate_module_name(module_name)
    if err:
        return json.dumps({"error": err}, ensure_ascii=False)

    # Check that the .py file actually exists on disk
    expected_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        module_name.split(".")[1] + ".py",
    )
    if not os.path.isfile(expected_path):
        return json.dumps(
            {"error": f"File not found: {expected_path}"},
            ensure_ascii=False,
        )

    # --- Snapshot registry state before import ---
    tools_before = set(registry.get_all_tool_names())
    old_entry = _MODULE_TOOL_MAP.get(module_name, {})
    old_module_tools = old_entry.get("tools", set())
    old_toolset = old_entry.get("toolset")

    # --- Import or reload ---
    try:
        # Flush stale bytecode caches so reload picks up latest .py content
        importlib.invalidate_caches()

        is_reload = module_name in sys.modules
        if is_reload:
            mod = importlib.reload(sys.modules[module_name])
            action = "reloaded"
        else:
            mod = importlib.import_module(module_name)
            action = "loaded"
    except Exception as exc:
        return json.dumps(
            {"error": f"Import failed: {type(exc).__name__}: {exc}"},
            ensure_ascii=False,
        )

    # --- Detect what was registered ---
    tools_after = set(registry.get_all_tool_names())
    new_tools = sorted(tools_after - tools_before)

    # For reloads, tool names already existed so they won't appear in the
    # diff. Use the module-to-tools map to identify this module's tools.
    if is_reload and not new_tools:
        # Re-scan: tools this module owns are those it registered before,
        # plus any genuinely new ones from the diff.
        current_module_tools = set()
        for name in old_module_tools:
            if registry.get_toolset_for_tool(name) is not None:
                current_module_tools.add(name)
        new_tools = sorted(current_module_tools)

    # Detect tools removed from a reloaded module (were in old set, no
    # longer re-registered by this module after reload).
    removed_tools = []
    if is_reload and old_module_tools:
        still_registered = set()
        for name in old_module_tools:
            if registry.get_toolset_for_tool(name) is not None:
                still_registered.add(name)
        removed_tools = sorted(old_module_tools - still_registered)

    # --- Filter removed_tools: only clean up tools not owned by another module ---
    # NOTE: _MODULE_TOOL_MAP is updated AFTER this check so the current
    # module still has its old entry during the ownership scan.
    truly_removed = []
    for tool_name in removed_tools:
        owned_elsewhere = any(
            tool_name in entry.get("tools", set())
            for mod, entry in _MODULE_TOOL_MAP.items()
            if mod != module_name
        )
        if owned_elsewhere:
            logger.debug(
                "Tool '%s' removed from %s but still owned by another module; keeping",
                tool_name, module_name,
            )
        else:
            truly_removed.append(tool_name)
            # Remove stale entry from the registry itself
            if tool_name in registry._tools:
                del registry._tools[tool_name]
    removed_tools = truly_removed

    # --- Update module→tools mapping (after ownership check) ---
    _MODULE_TOOL_MAP[module_name] = {"tools": set(new_tools), "toolset": toolset}

    # --- Check for built-in collisions (defense-in-depth) ---
    collisions = [t for t in new_tools if t in _BUILTIN_TOOL_NAMES]
    if collisions:
        logger.warning(
            "Dynamic module %s registered tools that shadow built-ins: %s",
            module_name, collisions,
        )

    # --- Warn if module registered nothing ---
    if not new_tools:
        return json.dumps({
            "error": (
                f"Module '{module_name}' imported successfully but did not "
                "register any tools via registry.register(). Ensure the "
                "module calls registry.register() at the top level."
            ),
        }, ensure_ascii=False)

    # --- Update toolsets and platform tool lists ---
    from toolsets import _HERMES_CORE_TOOLS, TOOLSETS

    if add_to_all_platforms:
        for tool_name in new_tools:
            if tool_name not in _HERMES_CORE_TOOLS:
                _HERMES_CORE_TOOLS.append(tool_name)

        # Clean up removed tools from _HERMES_CORE_TOOLS
        for tool_name in removed_tools:
            try:
                _HERMES_CORE_TOOLS.remove(tool_name)
            except ValueError:
                pass

    # Clean old toolset if module migrated to a different one
    if old_toolset and old_toolset != toolset and old_toolset in TOOLSETS:
        old_ts_tools = set(TOOLSETS[old_toolset].get("tools", []))
        old_ts_tools -= set(removed_tools)
        if old_ts_tools:
            TOOLSETS[old_toolset]["tools"] = sorted(old_ts_tools)
        else:
            del TOOLSETS[old_toolset]

    # Always create/update the toolset in TOOLSETS so tools are reachable
    # via resolve_toolset() regardless of add_to_all_platforms.
    if toolset not in TOOLSETS:
        TOOLSETS[toolset] = {
            "description": f"Dynamically loaded tools ({toolset})",
            "tools": list(new_tools),
            "includes": [],
        }
    else:
        existing_tools = set(TOOLSETS[toolset].get("tools", []))
        existing_tools.update(new_tools)
        existing_tools -= set(removed_tools)
        TOOLSETS[toolset]["tools"] = sorted(existing_tools)

    # --- Refresh stale backward-compat constants in model_tools ---
    try:
        import model_tools
        model_tools.TOOL_TO_TOOLSET_MAP = registry.get_tool_to_toolset_map()
        model_tools.TOOLSET_REQUIREMENTS = registry.get_toolset_requirements()
    except Exception as exc:
        logger.debug("Could not refresh model_tools constants: %s", exc)

    logger.info(
        "reload_tools: %s module '%s' — tools: %s",
        action, module_name, new_tools,
    )

    result = {
        "status": "ok",
        "action": action,
        "module": module_name,
        "new_tools": new_tools,
        "toolset": toolset,
        "file": expected_path,
    }
    if removed_tools:
        result["removed_tools"] = removed_tools
    if collisions:
        result["warning"] = (
            f"These tools shadow built-in names: {collisions}. "
            "The dynamic versions are now active."
        )

    return json.dumps(result, ensure_ascii=False)


def check_reload_tools_requirements() -> bool:
    """Always available — no external dependencies."""
    return True


# =============================================================================
# OpenAI Function-Calling Schema
# =============================================================================

RELOAD_TOOLS_SCHEMA = {
    "name": "reload_tools",
    "description": (
        "Load or reload a Python tool module into the live tool registry, "
        "making new tools available immediately on the next turn.\n\n"
        "**IMPORTANT: Safety pipeline — follow these steps before calling reload_tools:**\n\n"
        "1. Use `write_file` to create/update the tool module at `tools/<name>.py`\n"
        "2. Use `terminal` to validate in a subprocess:\n"
        '   `python -c "import importlib; importlib.import_module(\'tools.<name>\')"`\n'
        "   This catches syntax errors, missing imports, and bad register() calls "
        "without risking the live process.\n"
        "3. Use `terminal` to test the handler in a subprocess:\n"
        '   `python -c "from tools.<name> import <handler>; print(<handler>({...}))"`\n'
        "   This verifies the handler returns valid JSON.\n"
        "4. Only after steps 2-3 succeed, call `reload_tools(module_name='tools.<name>')`\n\n"
        "Steps 2-3 run in isolated subprocesses — if they crash, the gateway is "
        "unaffected. Step 4 runs in-process but is safe because the module is "
        "already validated.\n\n"
        "The module must call `registry.register()` at the top level (like all "
        "hermes-agent tools). After reload, new tools appear in the next "
        "`get_tool_definitions()` call automatically."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "module_name": {
                "type": "string",
                "description": (
                    "Python module path, e.g. 'tools.weather_tool'. "
                    "Must be 'tools.<name>' (exactly two parts). "
                    "The corresponding .py file must exist on disk."
                ),
            },
            "toolset": {
                "type": "string",
                "description": (
                    "Toolset name to register the new tools under. "
                    "Defaults to 'dynamic'."
                ),
                "default": "dynamic",
            },
            "add_to_all_platforms": {
                "type": "boolean",
                "description": (
                    "If true, append new tool names to _HERMES_CORE_TOOLS "
                    "so they're available on all platforms (CLI, Telegram, etc). "
                    "Defaults to true."
                ),
                "default": True,
            },
        },
        "required": ["module_name"],
    },
}


# --- Registry ---
registry.register(
    name="reload_tools",
    toolset="meta",
    schema=RELOAD_TOOLS_SCHEMA,
    handler=reload_tools_handler,
    check_fn=check_reload_tools_requirements,
)
