"""Tree-sitter based Java parser for extracting AST information."""

from __future__ import annotations

from tree_sitter import Node, Tree
from tree_sitter_languages import get_language, get_parser

JAVA_LANGUAGE = get_language("java")

# Pre-compiled queries for common AST patterns

# Find import declarations
IMPORT_QUERY = JAVA_LANGUAGE.query("""
(import_declaration
  (scoped_identifier) @import_path)
""")

# Find method/constructor declarations (function bodies to analyze)
METHOD_DECL_QUERY = JAVA_LANGUAGE.query("""
(method_declaration
  name: (identifier) @method_name
  body: (block) @body)
""")

# Find class declarations and their superclass
CLASS_DECL_QUERY = JAVA_LANGUAGE.query("""
(class_declaration
  name: (identifier) @class_name
  (superclass (type_identifier) @superclass)?)
""")


def parse_java(source: bytes) -> Tree:
    """Parse Java source code into a tree-sitter AST."""
    parser = get_parser("java")
    return parser.parse(source)


def get_node_text(node: Node, source: bytes) -> str:
    """Extract the text of an AST node from the source."""
    return source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def find_imports(tree: Tree, source: bytes) -> dict[str, str]:
    """Extract import statements, returning a map of simple name -> fully qualified name.

    e.g., {"DecompInterface": "ghidra.app.decompiler.DecompInterface"}
    """
    imports: dict[str, str] = {}
    captures = IMPORT_QUERY.captures(tree.root_node)

    for node, name in captures:
        fqn = get_node_text(node, source)
        # Simple name is the last component
        simple_name = fqn.rsplit(".", 1)[-1]
        # Wildcard imports (e.g., ghidra.program.model.listing.*)
        if simple_name == "*":
            continue
        imports[simple_name] = fqn

    return imports


def find_method_bodies(tree: Tree, source: bytes) -> list[tuple[str, Node]]:
    """Find all method declarations, returning (method_name, body_node) pairs."""
    results = []
    captures = METHOD_DECL_QUERY.captures(tree.root_node)

    # Captures come in pairs: (method_name, body) per match
    names = [(node, name) for node, name in captures if name == "method_name"]
    bodies = [(node, name) for node, name in captures if name == "body"]

    for (name_node, _), (body_node, _) in zip(names, bodies):
        method_name = get_node_text(name_node, source)
        results.append((method_name, body_node))

    return results


def find_superclass(tree: Tree, source: bytes) -> str | None:
    """Find the superclass of the first class declaration, if any."""
    captures = CLASS_DECL_QUERY.captures(tree.root_node)
    for node, name in captures:
        if name == "superclass":
            return get_node_text(node, source)
    return None
