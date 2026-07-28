"""Back-compat re-export shim for the agent graph package.

This module used to hold the whole graph; its contents now live in
purpose-named modules and this file only re-exports them so legacy import
paths (``from src.services.agent.graph import …``) keep resolving:

- Topology + builders: ``_builders`` (``compile_agent_graph``,
  ``create_graph``, ``build_agent_graph``, ``should_continue``,
  ``MAX_TOOL_LOOPS``, ``MAX_ERRORS``)
- Main-graph nodes: ``_nodes_llm`` / ``_nodes_tools`` / ``_nodes_rag`` /
  ``_nodes_classify`` / ``_nodes_memory``
- Message sanitizer: ``_sanitize`` (``_sanitize_messages``)
- Main chat LLM construction: ``llm_factory`` (``_build_llm``)
- Prompts + intent hints: ``_prompts``
- UUID extraction: ``_uuid`` (``_extract_project_id_from_text``)

The actual topology:
  preprocessing_node → [route_by_intent] → research/writing/data subgraphs
  or planner_node → llm_node → [should_continue] → tool_node /
  interrupt_node / force_synthesis_node / reflection_gate → memory_save_node

New code should import from the real homes; this shim is scheduled for
deletion once the remaining callers are repointed.
"""

# Graph builders + conditional edges
from src.services.agent._builders import (  # noqa: F401
    MAX_ERRORS,
    MAX_TOOL_LOOPS,
    after_interrupt,
    build_agent_graph,
    compile_agent_graph,
    create_graph,
    should_continue,
)

# Intent classification + parallel preprocessing
from src.services.agent._nodes_classify import (  # noqa: F401
    _classify_core,
    _extract_prior_tool,
    intent_classifier_node,
    preprocessing_node,
    route_by_intent,
)

# Intent-specific tool subsets + main LLM node
from src.services.agent._nodes_llm import (  # noqa: F401
    GENERAL_TOOLS_NAMES,
    KG_TOOLS_NAMES,
    RESEARCH_TOOLS_NAMES,
    WRITING_TOOLS_NAMES,
    _get_tools_for_intent,
    llm_node,
)

# Memory nodes
from src.services.agent._nodes_memory import (  # noqa: F401
    memory_retrieval_node,
    memory_save_node,
)

# RAG node + retrieval helpers
from src.services.agent._nodes_rag import (  # noqa: F401
    _is_retrieval_query,
    _legacy_hybrid_search_fallback,
    _shape_do_kb_context,
    _try_primary_do_kb_read,
    is_conversational,
    rag_node,
)

# Tool execution + interrupt + concurrency constants
# Tool-executor indirection + JSON helper (moved to _nodes_tools).
# NOTE: the mutable ``execute_tool`` module global intentionally does NOT
# re-export — patch ``src.services.agent._nodes_tools.execute_tool`` (or
# ``tools_impl.execute_tool``) instead; a re-exported copy here would be a
# stale alias that patches silently miss.
from src.services.agent._nodes_tools import (  # noqa: F401
    _NO_OUTER_RETRY_TOOLS,
    _SLOW_TOOL_TIMEOUT_SECONDS,
    _SLOW_TOOLS,
    AGENT_LLM_TIMEOUT_SECONDS,
    DESTRUCTIVE_TOOLS,
    TOOL_TIMEOUT_SECONDS,
    _execute_single_tool,
    _get_execute_tool,
    _get_tool_semaphore,
    _safe_json_loads,
    interrupt_node,
    make_filtered_tool_node,
    tool_node,
)

# Prompt content + render helpers
# Intent classifier hints
from src.services.agent._prompts import (  # noqa: F401
    _LLM_NODE_STATIC_PROMPT,
    INTENT_KEYWORDS,
    INTENT_PRIORITY,
    INTENT_PROMPTS,
    SHARED_AGENT_RULES,
    _build_page_context_line,
    _merge_run_config,
    _runtime_model_line,
)

# Message sanitizer (moved to _sanitize)
from src.services.agent._sanitize import (  # noqa: F401
    _TOOL_PLACEHOLDER_CONTENT,
    _sanitize_messages,
    _tool_call_id,
)

# UUID extraction (moved to _uuid)
from src.services.agent._uuid import _extract_project_id_from_text  # noqa: F401

# Main chat LLM construction (moved to llm_factory)
from src.services.agent.llm_factory import _LLM_CACHE, _build_llm  # noqa: F401
