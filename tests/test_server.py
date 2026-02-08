"""Tests for MCP server tool functions."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from ghidra_workflow_mcp.config import Config
from ghidra_workflow_mcp.extractor.call_chain import extract_workflows_from_source
from ghidra_workflow_mcp.extractor.models import SourceFile, TrustLevel
from ghidra_workflow_mcp.indexer.search import WorkflowSearcher
from ghidra_workflow_mcp.indexer.store import (
    build_api_class_index,
    build_workflow_index,
    get_client,
)
from ghidra_workflow_mcp.server import get_api_doc, get_workflows, list_related_apis

KNOWN_CLASSES = {
    "DecompInterface", "DecompileResults", "Function", "Program",
    "Address", "Listing", "TaskMonitor", "Reference", "ReferenceManager",
    "FunctionIterator", "GhidraScript", "HighFunction",
}

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def server_with_index():
    """Set up a test index and patch the server's searcher."""
    config = Config()
    all_workflows = []
    for java_file in FIXTURES_DIR.glob("*.java"):
        sf = SourceFile(path=java_file, trust_level=TrustLevel.HIGHEST, category="test")
        workflows = extract_workflows_from_source(sf, KNOWN_CLASSES, config)
        all_workflows.extend(workflows)

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_chroma"
        client = get_client(db_path)
        build_workflow_index(client, all_workflows)
        build_api_class_index(client, all_workflows)

        searcher = WorkflowSearcher(db_path)
        with patch("ghidra_workflow_mcp.server._searcher", searcher):
            yield


def test_get_workflows_returns_results(server_with_index):
    result = get_workflows("decompile a function to C code")
    assert "Result 1" in result
    assert "DecompInterface" in result


def test_get_workflows_no_match(server_with_index):
    # Even obscure queries should return something (semantic search is fuzzy)
    result = get_workflows("zzzzz_nonexistent_zzzzz")
    # Should still return something or a no-match message
    assert isinstance(result, str)


def test_get_api_doc_returns_results(server_with_index):
    result = get_api_doc("DecompInterface")
    assert "DecompInterface" in result
    assert "Methods:" in result


def test_list_related_apis_returns_results(server_with_index):
    result = list_related_apis("DecompInterface")
    assert "DecompInterface" in result
    assert "DecompileResults" in result
