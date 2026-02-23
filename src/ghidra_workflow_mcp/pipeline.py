"""Shared pipeline for building the Ghidra workflow index."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from ghidra_workflow_mcp.config import Config


def build_index_pipeline(
    ghidra_path: Path | None = None,
    db_path: Path = Path("data/chroma_db"),
    max_files: int | None = None,
    progress: Callable[[str], None] = lambda _: None,
) -> None:
    """Run the full index-build pipeline.

    Args:
        ghidra_path: Path to a local Ghidra source tree. If None, Ghidra is
                     cloned from GitHub (may take several minutes).
        db_path: Directory for ChromaDB persistent storage.
        max_files: Limit files processed (useful for testing).
        progress: Callable invoked with each status message.
    """
    from ghidra_workflow_mcp.collector.ghidra_source import (
        build_known_class_names,
        clone_ghidra,
        detect_ghidra_version,
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

    if config.ghidra_source_path:
        ghidra_root = config.ghidra_source_path
    else:
        ghidra_root = clone_ghidra(config, Path("data/ghidra_source"))
    progress(f"Using Ghidra source at: {ghidra_root}")

    ghidra_version = detect_ghidra_version(ghidra_root)
    progress(f"Ghidra version: {ghidra_version}")

    progress("Scanning for known Ghidra class names...")
    known_classes = build_known_class_names(ghidra_root)
    progress(f"Found {len(known_classes)} known Ghidra classes")

    progress("Enumerating Java source files...")
    source_files = enumerate_java_files(ghidra_root, config)
    progress(f"Found {len(source_files)} Java files to process")

    progress("Extracting workflows...")
    all_workflows = []
    for i, sf in enumerate(source_files):
        if (i + 1) % 500 == 0:
            progress(f"  Processed {i + 1}/{len(source_files)} files...")
        workflows = extract_workflows_from_source(sf, known_classes, config)
        all_workflows.extend(workflows)
    progress(f"Extracted {len(all_workflows)} workflows")

    progress("Building ChromaDB index...")
    client = get_client(config.db_path)
    build_workflow_index(client, all_workflows, ghidra_version=ghidra_version)
    build_api_class_index(client, all_workflows)
    progress(f"Index built at: {config.db_path}")
    progress("Done!")
