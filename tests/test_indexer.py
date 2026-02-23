"""Tests for the ChromaDB indexer and search."""

import tempfile
from pathlib import Path

import pytest

from ghidra_api_mcp.config import Config
from ghidra_api_mcp.extractor.call_chain import extract_workflows_from_source
from ghidra_api_mcp.extractor.models import SourceFile, TrustLevel
from ghidra_api_mcp.indexer.search import WorkflowSearcher
from ghidra_api_mcp.indexer.store import (
    build_api_class_index,
    build_workflow_index,
    get_client,
)

KNOWN_CLASSES = {
    "DecompInterface", "DecompileResults", "Function", "Program",
    "Address", "Listing", "TaskMonitor", "Reference", "ReferenceManager",
    "FunctionIterator", "GhidraScript", "HighFunction",
}


@pytest.fixture
def test_workflows(fixtures_dir):
    """Extract workflows from all test fixtures."""
    config = Config()
    all_workflows = []
    for java_file in fixtures_dir.glob("*.java"):
        sf = SourceFile(path=java_file, trust_level=TrustLevel.HIGHEST, category="test")
        workflows = extract_workflows_from_source(sf, KNOWN_CLASSES, config)
        all_workflows.extend(workflows)
    return all_workflows


@pytest.fixture
def indexed_db(test_workflows):
    """Create a temporary ChromaDB with indexed test workflows."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_chroma"
        client = get_client(db_path)
        build_workflow_index(client, test_workflows)
        build_api_class_index(client, test_workflows)
        yield db_path


def test_build_index_succeeds(test_workflows):
    """Index building should not raise errors."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_chroma"
        client = get_client(db_path)
        build_workflow_index(client, test_workflows)
        build_api_class_index(client, test_workflows)


def test_search_workflows_decompile(indexed_db):
    searcher = WorkflowSearcher(indexed_db)
    results = searcher.search_workflows("decompile a function")

    assert len(results) > 0
    # The decompile workflow should be in the results
    top = results[0]
    assert "DecompInterface" in top.get("classes_used", "")


def test_search_workflows_xref(indexed_db):
    searcher = WorkflowSearcher(indexed_db)
    results = searcher.search_workflows("cross references to an address")

    assert len(results) > 0
    # Should find xref-related workflows
    all_classes = " ".join(r.get("classes_used", "") for r in results)
    assert "ReferenceManager" in all_classes


def test_get_api_doc_exact(indexed_db):
    searcher = WorkflowSearcher(indexed_db)
    results = searcher.get_api_doc("DecompInterface")

    assert len(results) > 0
    assert any(r.get("class_name") == "DecompInterface" for r in results)


def test_get_api_doc_fuzzy(indexed_db):
    searcher = WorkflowSearcher(indexed_db)
    results = searcher.get_api_doc("decompile")

    assert len(results) > 0


def test_list_related_apis(indexed_db):
    searcher = WorkflowSearcher(indexed_db)
    result = searcher.list_related_apis("DecompInterface")

    assert result["queried"] == "DecompInterface"
    assert result["workflow_count"] > 0
    related_names = {r["class"] for r in result["related"]}
    # DecompileResults should co-occur with DecompInterface
    assert "DecompileResults" in related_names


def test_empty_index():
    """Searching an empty index should not crash."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "empty_chroma"
        client = get_client(db_path)
        build_workflow_index(client, [])
        build_api_class_index(client, [])

        searcher = WorkflowSearcher(db_path)
        results = searcher.search_workflows("anything")
        assert results == []
