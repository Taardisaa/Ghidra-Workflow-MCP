"""Tests for the call chain extractor."""

from pathlib import Path

from ghidra_api_mcp.config import Config
from ghidra_api_mcp.extractor.call_chain import extract_workflows_from_source
from ghidra_api_mcp.extractor.models import SourceFile, TrustLevel


def _make_source_file(path: Path, trust: TrustLevel = TrustLevel.HIGHEST) -> SourceFile:
    return SourceFile(path=path, trust_level=trust, category="test")


# A minimal set of known classes for testing
KNOWN_CLASSES = {
    "DecompInterface", "DecompileResults", "Function", "Program",
    "Address", "Listing", "TaskMonitor", "Reference", "ReferenceManager",
    "FunctionIterator", "GhidraScript", "HighFunction",
}


def test_extract_decompile_workflow(fixtures_dir):
    sf = _make_source_file(fixtures_dir / "DecompileExample.java")
    config = Config()
    workflows = extract_workflows_from_source(sf, KNOWN_CLASSES, config)

    assert len(workflows) == 1
    w = workflows[0]

    assert w.function_name == "decompileFunction"
    assert w.trust_level == TrustLevel.HIGHEST

    # Should have multiple Ghidra API calls
    assert len(w.calls) >= 4

    # Check that key classes are detected
    assert "DecompInterface" in w.ghidra_classes_used
    assert "DecompileResults" in w.ghidra_classes_used

    # Check call ordering: DecompInterface constructor should come first
    class_methods = [(c.class_name, c.method_name) for c in w.calls]
    assert class_methods[0] == ("DecompInterface", "<init>")

    # openProgram should follow the constructor
    assert any(
        cm == ("DecompInterface", "openProgram") for cm in class_methods
    )


def test_extract_decompile_data_flow(fixtures_dir):
    sf = _make_source_file(fixtures_dir / "DecompileExample.java")
    config = Config()
    workflows = extract_workflows_from_source(sf, KNOWN_CLASSES, config)

    w = workflows[0]

    # There should be data flow edges
    assert len(w.data_flow) > 0

    # The ifc variable should connect constructor to openProgram
    ifc_edges = [e for e in w.data_flow if e.variable_name == "ifc"]
    assert len(ifc_edges) > 0
    # The constructor output feeds into subsequent calls on ifc
    assert any(e.role == "receiver" for e in ifc_edges)


def test_extract_xref_workflows(fixtures_dir):
    sf = _make_source_file(fixtures_dir / "XrefExample.java")
    config = Config()
    workflows = extract_workflows_from_source(sf, KNOWN_CLASSES, config)

    # Should extract 2 workflows (getXrefsTo and getXrefsFrom)
    assert len(workflows) == 2
    names = {w.function_name for w in workflows}
    assert names == {"getXrefsTo", "getXrefsFrom"}

    for w in workflows:
        assert "ReferenceManager" in w.ghidra_classes_used


def test_extract_ghidra_script(fixtures_dir):
    sf = _make_source_file(fixtures_dir / "SimpleScript.java")
    config = Config()
    workflows = extract_workflows_from_source(sf, KNOWN_CLASSES, config)

    assert len(workflows) >= 1
    w = workflows[0]
    assert w.function_name == "run"

    # Should detect GhidraScript base class methods
    class_methods = [(c.class_name, c.method_name) for c in w.calls]
    assert any(cm[0] == "GhidraScript" and cm[1] == "println" for cm in class_methods)


def test_workflow_display_text(fixtures_dir):
    sf = _make_source_file(fixtures_dir / "DecompileExample.java")
    config = Config()
    workflows = extract_workflows_from_source(sf, KNOWN_CLASSES, config)

    w = workflows[0]
    text = w.to_display_text()

    assert "Workflow: decompileFunction" in text
    assert "1." in text  # First step numbered


def test_workflow_embedding_text(fixtures_dir):
    sf = _make_source_file(fixtures_dir / "DecompileExample.java")
    config = Config()
    workflows = extract_workflows_from_source(sf, KNOWN_CLASSES, config)

    w = workflows[0]
    text = w.to_embedding_text()

    assert "DecompInterface" in text
    assert "Call chain:" in text
    assert "decompileFunction" in text


def test_workflow_id_is_stable(fixtures_dir):
    sf = _make_source_file(fixtures_dir / "DecompileExample.java")
    config = Config()

    workflows1 = extract_workflows_from_source(sf, KNOWN_CLASSES, config)
    workflows2 = extract_workflows_from_source(sf, KNOWN_CLASSES, config)

    assert workflows1[0].id == workflows2[0].id


def test_min_calls_filter(fixtures_dir):
    """Workflows with fewer than 2 calls should be filtered out."""
    sf = _make_source_file(fixtures_dir / "DecompileExample.java")
    config = Config()
    workflows = extract_workflows_from_source(sf, KNOWN_CLASSES, config)

    for w in workflows:
        assert len(w.calls) >= 2
