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


@mcp.tool()
def get_index_info() -> str:
    """Return metadata about the currently built index.

    Shows the Ghidra version the index was built from, when it was indexed,
    and how many workflows and API classes are stored.
    """
    from ghidra_workflow_mcp.indexer.store import get_client
    from ghidra_workflow_mcp.indexer.store import get_index_info as _get_info

    config = Config()
    info = _get_info(get_client(config.db_path))

    if info["workflow_count"] == 0 and info["ghidra_version"] == "unknown":
        return "Index is empty. Run initialize_index() to build it."

    return (
        f"Ghidra version : {info['ghidra_version']}\n"
        f"Indexed at     : {info['indexed_at']}\n"
        f"Workflows      : {info['workflow_count']}\n"
        f"API classes    : {info['api_class_count']}"
    )


@mcp.tool()
def clear_index() -> str:
    """Delete the workflow index (ChromaDB collections).

    Removes all indexed data. You will need to run initialize_index() again
    before the query tools return results.
    """
    from ghidra_workflow_mcp.indexer.store import clear_index as _clear
    from ghidra_workflow_mcp.indexer.store import get_client

    config = Config()
    _clear(get_client(config.db_path))

    global _searcher
    _searcher = None

    return "Index cleared. Run initialize_index() to rebuild."


@mcp.tool()
def initialize_index(ghidra_path: str = "") -> str:
    """Build the Ghidra API workflow index (RAG database).

    Downloads Ghidra source from GitHub (or uses a local copy) and builds
    the searchable workflow index. Must be run once before the other tools
    will return results.

    WARNING: This is a long-running operation. Cloning Ghidra and processing
    its source files may take 10–30 minutes depending on network and CPU speed.

    Args:
        ghidra_path: Optional absolute path to a local Ghidra source tree.
                     Leave empty to clone from GitHub automatically.
    """
    from pathlib import Path

    from ghidra_workflow_mcp.pipeline import build_index_pipeline

    messages: list[str] = []
    build_index_pipeline(
        ghidra_path=Path(ghidra_path) if ghidra_path else None,
        progress=messages.append,
    )

    # Reset the cached searcher so it loads the freshly built index
    global _searcher
    _searcher = None

    return "\n".join(messages)


def run_server():
    """Start the MCP server with stdio transport."""
    mcp.run(transport="stdio")
