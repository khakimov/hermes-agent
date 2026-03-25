#!/usr/bin/env python3
"""
Tools Package

This package contains all the specific tool implementations for the Hermes Agent.
Each module provides specialized functionality for different capabilities.

Tool discovery and registration is handled by model_tools._discover_tools(),
which imports each module in a try/except block. The imports below are
convenience re-exports for code that does ``from tools import ...``.
Any missing optional dependency (firecrawl, fal_client, etc.) is silently
skipped — the tool simply won't appear in the registry.
"""

import logging as _log

_logger = _log.getLogger(__name__)

def _try_import(block, name):
    """Run an import block, swallowing ImportError for optional deps."""
    try:
        block()
    except (ImportError, Exception) as e:
        _logger.debug("tools.__init__: skipping %s: %s", name, e)

# --- Web tools ---
def _web():
    global web_search_tool, web_extract_tool, web_crawl_tool, check_firecrawl_api_key
    from .web_tools import web_search_tool, web_extract_tool, web_crawl_tool, check_firecrawl_api_key
_try_import(_web, "web_tools")

# --- Terminal tool ---
def _terminal():
    global terminal_tool, check_terminal_requirements, cleanup_vm
    global cleanup_all_environments, get_active_environments_info
    global register_task_env_overrides, clear_task_env_overrides, TERMINAL_TOOL_DESCRIPTION
    from .terminal_tool import (
        terminal_tool, check_terminal_requirements, cleanup_vm,
        cleanup_all_environments, get_active_environments_info,
        register_task_env_overrides, clear_task_env_overrides, TERMINAL_TOOL_DESCRIPTION
    )
_try_import(_terminal, "terminal_tool")

# --- Vision tools ---
def _vision():
    global vision_analyze_tool, check_vision_requirements
    from .vision_tools import vision_analyze_tool, check_vision_requirements
_try_import(_vision, "vision_tools")

# --- MoA tool ---
def _moa():
    global mixture_of_agents_tool, check_moa_requirements
    from .mixture_of_agents_tool import mixture_of_agents_tool, check_moa_requirements
_try_import(_moa, "mixture_of_agents_tool")

# --- Image generation tool ---
def _image():
    global image_generate_tool, check_image_generation_requirements
    from .image_generation_tool import image_generate_tool, check_image_generation_requirements
_try_import(_image, "image_generation_tool")

# --- Skills tools ---
def _skills():
    global skills_list, skill_view, check_skills_requirements, SKILLS_TOOL_DESCRIPTION
    from .skills_tool import skills_list, skill_view, check_skills_requirements, SKILLS_TOOL_DESCRIPTION
_try_import(_skills, "skills_tool")

def _skill_mgr():
    global skill_manage, check_skill_manage_requirements, SKILL_MANAGE_SCHEMA
    from .skill_manager_tool import skill_manage, check_skill_manage_requirements, SKILL_MANAGE_SCHEMA
_try_import(_skill_mgr, "skill_manager_tool")

# --- Browser automation tools ---
def _browser():
    global browser_navigate, browser_snapshot, browser_click, browser_type
    global browser_scroll, browser_back, browser_press, browser_close
    global browser_get_images, browser_vision, cleanup_browser
    global cleanup_all_browsers, get_active_browser_sessions
    global check_browser_requirements, BROWSER_TOOL_SCHEMAS
    from .browser_tool import (
        browser_navigate, browser_snapshot, browser_click, browser_type,
        browser_scroll, browser_back, browser_press, browser_close,
        browser_get_images, browser_vision, cleanup_browser,
        cleanup_all_browsers, get_active_browser_sessions,
        check_browser_requirements, BROWSER_TOOL_SCHEMAS
    )
_try_import(_browser, "browser_tool")

# --- Cronjob tools ---
def _cronjob():
    global cronjob, schedule_cronjob, list_cronjobs, remove_cronjob
    global check_cronjob_requirements, get_cronjob_tool_definitions
    global CRONJOB_SCHEMA
    from .cronjob_tools import (
        cronjob, schedule_cronjob, list_cronjobs, remove_cronjob,
        check_cronjob_requirements, get_cronjob_tool_definitions,
        CRONJOB_SCHEMA,
    )
_try_import(_cronjob, "cronjob_tools")

# --- RL Training tools ---
def _rl():
    global rl_list_environments, rl_select_environment, rl_get_current_config
    global rl_edit_config, rl_start_training, rl_check_status
    global rl_stop_training, rl_get_results, rl_list_runs, rl_test_inference
    global check_rl_api_keys, get_missing_keys
    from .rl_training_tool import (
        rl_list_environments, rl_select_environment, rl_get_current_config,
        rl_edit_config, rl_start_training, rl_check_status,
        rl_stop_training, rl_get_results, rl_list_runs, rl_test_inference,
        check_rl_api_keys, get_missing_keys,
    )
_try_import(_rl, "rl_training_tool")

# --- File tools ---
def _file():
    global read_file_tool, write_file_tool, patch_tool, search_tool
    global get_file_tools, clear_file_ops_cache
    from .file_tools import (
        read_file_tool, write_file_tool, patch_tool, search_tool,
        get_file_tools, clear_file_ops_cache,
    )
_try_import(_file, "file_tools")

# --- TTS tools ---
def _tts():
    global text_to_speech_tool, check_tts_requirements
    from .tts_tool import text_to_speech_tool, check_tts_requirements
_try_import(_tts, "tts_tool")

# --- Todo tool ---
def _todo():
    global todo_tool, check_todo_requirements, TODO_SCHEMA, TodoStore
    from .todo_tool import todo_tool, check_todo_requirements, TODO_SCHEMA, TodoStore
_try_import(_todo, "todo_tool")

# --- Clarify tool ---
def _clarify():
    global clarify_tool, check_clarify_requirements, CLARIFY_SCHEMA
    from .clarify_tool import clarify_tool, check_clarify_requirements, CLARIFY_SCHEMA
_try_import(_clarify, "clarify_tool")

# --- Code execution tool ---
def _code_exec():
    global execute_code, check_sandbox_requirements, EXECUTE_CODE_SCHEMA
    from .code_execution_tool import execute_code, check_sandbox_requirements, EXECUTE_CODE_SCHEMA
_try_import(_code_exec, "code_execution_tool")

# --- Delegate tool ---
def _delegate():
    global delegate_task, check_delegate_requirements, DELEGATE_TASK_SCHEMA
    from .delegate_tool import delegate_task, check_delegate_requirements, DELEGATE_TASK_SCHEMA
_try_import(_delegate, "delegate_tool")


# File tools have no external requirements - they use the terminal backend
def check_file_requirements():
    """File tools only require terminal backend to be available."""
    from .terminal_tool import check_terminal_requirements
    return check_terminal_requirements()

__all__ = [
    # Web tools
    'web_search_tool',
    'web_extract_tool',
    'web_crawl_tool',
    'check_firecrawl_api_key',
    # Terminal tools
    'terminal_tool',
    'check_terminal_requirements',
    'cleanup_vm',
    'cleanup_all_environments',
    'get_active_environments_info',
    'register_task_env_overrides',
    'clear_task_env_overrides',
    'TERMINAL_TOOL_DESCRIPTION',
    # Vision tools
    'vision_analyze_tool',
    'check_vision_requirements',
    # MoA tools
    'mixture_of_agents_tool',
    'check_moa_requirements',
    # Image generation tools
    'image_generate_tool',
    'check_image_generation_requirements',
    # Skills tools
    'skills_list',
    'skill_view',
    'check_skills_requirements',
    'SKILLS_TOOL_DESCRIPTION',
    # Skill management
    'skill_manage',
    'check_skill_manage_requirements',
    'SKILL_MANAGE_SCHEMA',
    # Browser automation tools
    'browser_navigate',
    'browser_snapshot',
    'browser_click',
    'browser_type',
    'browser_scroll',
    'browser_back',
    'browser_press',
    'browser_close',
    'browser_get_images',
    'browser_vision',
    'cleanup_browser',
    'cleanup_all_browsers',
    'get_active_browser_sessions',
    'check_browser_requirements',
    'BROWSER_TOOL_SCHEMAS',
    # Cronjob management tools (CLI-only)
    'cronjob',
    'schedule_cronjob',
    'list_cronjobs',
    'remove_cronjob',
    'check_cronjob_requirements',
    'get_cronjob_tool_definitions',
    'CRONJOB_SCHEMA',
    # RL Training tools
    'rl_list_environments',
    'rl_select_environment',
    'rl_get_current_config',
    'rl_edit_config',
    'rl_start_training',
    'rl_check_status',
    'rl_stop_training',
    'rl_get_results',
    'rl_list_runs',
    'rl_test_inference',
    'check_rl_api_keys',
    'get_missing_keys',
    # File manipulation tools
    'read_file_tool',
    'write_file_tool',
    'patch_tool',
    'search_tool',
    'get_file_tools',
    'clear_file_ops_cache',
    'check_file_requirements',
    # Text-to-speech tools
    'text_to_speech_tool',
    'check_tts_requirements',
    # Planning & task management tool
    'todo_tool',
    'check_todo_requirements',
    'TODO_SCHEMA',
    'TodoStore',
    # Clarifying questions tool
    'clarify_tool',
    'check_clarify_requirements',
    'CLARIFY_SCHEMA',
    # Code execution sandbox
    'execute_code',
    'check_sandbox_requirements',
    'EXECUTE_CODE_SCHEMA',
    # Subagent delegation
    'delegate_task',
    'check_delegate_requirements',
    'DELEGATE_TASK_SCHEMA',
]
