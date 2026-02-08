"""MCP server exposing Ghidra API workflow retrieval tools."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from ghidra_workflow_mcp.config import Config
from ghidra_workflow_mcp.indexer.search import WorkflowSearcher

# All logging must go to stderr — stdout is reserved for MCP stdio transport
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger(__name__)

mcp = FastMCP("ghidra-workflow")

# Lazy-initialized searcher (initialized on first tool call)
_searcher: WorkflowSearcher | None = None


def _get_searcher() -> WorkflowSearcher:
    global _searcher
    if _searcher is None:
        config = Config()
        _searcher = WorkflowSearcher(config.db_path)
    return _searcher


@mcp.tool()
def get_workflows(task_description: str) -> str:
    """Search for Ghidra API workflows matching a task description.

    Returns ranked workflow call chains showing the correct API call
    sequence for accomplishing the described task. Each result includes
    ordered API calls with data-flow dependencies and source code.

    Args:
        task_description: Natural language description of what you want
                          to accomplish, e.g. "decompile a function to C code"
    """
    searcher = _get_searcher()
    results = searcher.search_workflows(task_description, n_results=3)

    if not results:
        return "No matching workflows found for this task description."

    output_parts = []
    for i, r in enumerate(results, 1):
        output_parts.append(f"=== Result {i} (trust: {r.get('trust_level', '?')}) ===")
        output_parts.append(r.get("display_text", "(no display text)"))
        snippet = r.get("source_snippet", "")
        if snippet:
            output_parts.append(f"\nSource code:\n```java\n{snippet}\n```")
        output_parts.append("")

    return "\n".join(output_parts)


@mcp.tool()
def get_api_doc(name: str) -> str:
    """Look up Ghidra API documentation for a class or method.

    Supports fuzzy and partial matching — no fully qualified path needed.

    Args:
        name: Class name, method name, or keyword to search for.
              Examples: "DecompInterface", "decompileFunction", "Function"
    """
    searcher = _get_searcher()
    results = searcher.get_api_doc(name, n_results=5)

    if not results:
        return f"No API documentation found for '{name}'."

    output_parts = []
    for r in results:
        class_name = r.get("class_name", "?")
        methods = r.get("methods", "").split(",")
        workflow_count = r.get("workflow_count", 0)
        example_file = r.get("example_file", "")

        output_parts.append(f"## {class_name}")
        output_parts.append(f"Methods: {', '.join(methods)}")
        output_parts.append(f"Used in {workflow_count} extracted workflow(s)")
        if example_file:
            output_parts.append(f"Example: {example_file}")
        output_parts.append("")

    return "\n".join(output_parts)


@mcp.tool()
def list_related_apis(name: str) -> str:
    """Find Ghidra APIs commonly used alongside a given class or method.

    Returns co-occurring APIs based on real usage patterns in Ghidra source code.

    Args:
        name: A Ghidra class or method name, e.g. "DecompInterface"
    """
    searcher = _get_searcher()
    result = searcher.list_related_apis(name)

    if not result["related"]:
        return f"No related APIs found for '{name}'."

    output_parts = [
        f"APIs commonly used with {result['queried']} "
        f"(found in {result['workflow_count']} workflow(s)):",
        "",
    ]
    for item in result["related"]:
        output_parts.append(
            f"- {item['class']}: co-occurs in {item['co_occurrence_count']} workflow(s)"
        )

    return "\n".join(output_parts)


def run_server():
    """Start the MCP server with stdio transport."""
    mcp.run(transport="stdio")
