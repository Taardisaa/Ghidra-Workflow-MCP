"""CLI entry points for the Ghidra Workflow MCP server."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import click

from ghidra_workflow_mcp.config import Config

logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,
    format="%(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


@click.group()
def main():
    """Ghidra API Workflow Retrieval MCP Server."""


@main.command()
@click.option(
    "--ghidra-path",
    type=click.Path(exists=True, path_type=Path),
    help="Path to a local Ghidra source tree. If not provided, Ghidra will be cloned.",
)
@click.option(
    "--db-path",
    type=click.Path(path_type=Path),
    default="data/chroma_db",
    show_default=True,
    help="Path for ChromaDB storage.",
)
@click.option(
    "--max-files",
    type=int,
    default=None,
    help="Limit the number of Java files to process (for testing).",
)
def build_index(ghidra_path: Path | None, db_path: Path, max_files: int | None):
    """Build the workflow index from Ghidra source code."""
    from ghidra_workflow_mcp.collector.ghidra_source import (
        build_known_class_names,
        clone_ghidra,
        enumerate_java_files,
    )
    from ghidra_workflow_mcp.extractor.call_chain import extract_workflows_from_source
    from ghidra_workflow_mcp.indexer.store import (
        build_api_class_index,
        build_workflow_index,
        get_client,
    )

    config = Config(
        ghidra_source_path=ghidra_path,
        db_path=db_path,
        max_files=max_files,
    )

    # Step 1: Locate or clone Ghidra source
    if config.ghidra_source_path:
        ghidra_root = config.ghidra_source_path
    else:
        ghidra_root = clone_ghidra(config, Path("data/ghidra_source"))
    click.echo(f"Using Ghidra source at: {ghidra_root}")

    # Step 2: Build known class name set
    click.echo("Scanning for known Ghidra class names...")
    known_classes = build_known_class_names(ghidra_root)
    click.echo(f"Found {len(known_classes)} known Ghidra classes")

    # Step 3: Enumerate Java files
    click.echo("Enumerating Java source files...")
    source_files = enumerate_java_files(ghidra_root, config)
    click.echo(f"Found {len(source_files)} Java files to process")

    # Step 4: Extract workflows
    click.echo("Extracting workflows...")
    all_workflows = []
    for i, sf in enumerate(source_files):
        if (i + 1) % 500 == 0:
            click.echo(f"  Processed {i + 1}/{len(source_files)} files...")
        workflows = extract_workflows_from_source(sf, known_classes, config)
        all_workflows.extend(workflows)
    click.echo(f"Extracted {len(all_workflows)} workflows")

    # Step 5: Index into ChromaDB
    click.echo("Building ChromaDB index...")
    client = get_client(config.db_path)
    build_workflow_index(client, all_workflows)
    build_api_class_index(client, all_workflows)
    click.echo(f"Index built at: {config.db_path}")
    click.echo("Done!")


@main.command()
def serve():
    """Start the MCP server (stdio transport)."""
    from ghidra_workflow_mcp.server import run_server

    run_server()


@main.command()
@click.argument("query")
@click.option(
    "--db-path",
    type=click.Path(path_type=Path),
    default="data/chroma_db",
    show_default=True,
    help="Path to ChromaDB storage.",
)
@click.option(
    "--n-results",
    type=int,
    default=3,
    show_default=True,
    help="Number of results to return.",
)
def inspect(query: str, db_path: Path, n_results: int):
    """Test a query against the index without running MCP."""
    from ghidra_workflow_mcp.indexer.search import WorkflowSearcher

    searcher = WorkflowSearcher(db_path)
    results = searcher.search_workflows(query, n_results=n_results)

    if not results:
        click.echo("No results found.")
        return

    for i, r in enumerate(results, 1):
        click.echo(f"=== Result {i} (trust: {r.get('trust_level', '?')}) ===")
        click.echo(r.get("display_text", "(no display text)"))
        click.echo(f"\nSource: {r.get('file_path', '?')}")
        click.echo("---")


if __name__ == "__main__":
    main()
