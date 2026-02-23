"""Tests for the tree-sitter Java parser module."""

from ghidra_api_mcp.parser.java_parser import (
    find_imports,
    find_method_bodies,
    find_superclass,
    parse_java,
)


def test_parse_java_returns_tree(decompile_source):
    tree = parse_java(decompile_source)
    assert tree is not None
    assert tree.root_node.type == "program"


def test_parse_java_no_errors(decompile_source):
    tree = parse_java(decompile_source)
    assert not tree.root_node.has_error


def test_find_imports(decompile_source):
    tree = parse_java(decompile_source)
    imports = find_imports(tree, decompile_source)

    assert "DecompInterface" in imports
    assert imports["DecompInterface"] == "ghidra.app.decompiler.DecompInterface"
    assert "DecompileResults" in imports
    assert imports["DecompileResults"] == "ghidra.app.decompiler.DecompileResults"
    assert "Function" in imports
    assert imports["Function"] == "ghidra.program.model.listing.Function"


def test_find_method_bodies(decompile_source):
    tree = parse_java(decompile_source)
    methods = find_method_bodies(tree, decompile_source)

    assert len(methods) == 1
    name, body = methods[0]
    assert name == "decompileFunction"
    assert body.type == "block"


def test_find_superclass_when_present(simple_script_source):
    tree = parse_java(simple_script_source)
    superclass = find_superclass(tree, simple_script_source)
    assert superclass == "GhidraScript"


def test_find_superclass_when_absent(decompile_source):
    tree = parse_java(decompile_source)
    superclass = find_superclass(tree, decompile_source)
    assert superclass is None


def test_find_imports_xref(xref_source):
    tree = parse_java(xref_source)
    imports = find_imports(tree, xref_source)

    assert "ReferenceManager" in imports
    assert imports["ReferenceManager"] == "ghidra.program.model.symbol.ReferenceManager"
    assert "Reference" in imports


def test_find_multiple_methods(xref_source):
    tree = parse_java(xref_source)
    methods = find_method_bodies(tree, xref_source)

    assert len(methods) == 2
    names = {name for name, _ in methods}
    assert names == {"getXrefsTo", "getXrefsFrom"}
