"""Extract Ghidra API call chains from parsed Java ASTs."""

from __future__ import annotations

import logging
import re
from tree_sitter import Node

from ghidra_api_mcp.config import Config
from ghidra_api_mcp.extractor.models import (
    ApiCall,
    DataFlowEdge,
    SourceFile,
    TrustLevel,
    Workflow,
)
from ghidra_api_mcp.parser.java_parser import (
    find_imports,
    find_method_bodies,
    find_superclass,
    get_node_text,
    parse_java,
)

logger = logging.getLogger(__name__)

# Well-known GhidraScript fields mapped to their Ghidra types
_GHIDRA_SCRIPT_FIELDS: dict[str, str] = {
    "currentProgram": "Program",
    "currentAddress": "Address",
    "currentLocation": "ProgramLocation",
    "currentSelection": "ProgramSelection",
    "currentHighlight": "ProgramSelection",
}


def _is_ghidra_import(fqn: str) -> bool:
    """Check if a fully-qualified name belongs to Ghidra."""
    return fqn.startswith("ghidra.")


def _walk_nodes_by_offset(node: Node) -> list[Node]:
    """Recursively collect all descendant nodes, sorted by byte offset."""
    nodes = []
    cursor = node.walk()

    def _visit():
        nodes.append(cursor.node)
        if cursor.goto_first_child():
            _visit()
            while cursor.goto_next_sibling():
                _visit()
            cursor.goto_parent()

    _visit()
    nodes.sort(key=lambda n: n.start_byte)
    return nodes


def _extract_argument_identifiers(args_node: Node, source: bytes) -> list[str]:
    """Extract identifier names from an argument list node."""
    identifiers = []
    for child in args_node.named_children:
        if child.type == "identifier":
            identifiers.append(get_node_text(child, source))
        elif child.type == "field_access":
            # e.g., TaskMonitor.DUMMY — use full text
            identifiers.append(get_node_text(child, source))
    return identifiers


def _generate_description(
    function_name: str, classes_used: set[str], source_snippet: str
) -> str:
    """Auto-generate a workflow description from available context."""
    # Extract javadoc/comment above the method if present
    comment_match = re.search(
        r'/\*\*(.*?)\*/', source_snippet, re.DOTALL
    )
    if comment_match:
        comment = comment_match.group(1)
        # Clean up javadoc formatting
        comment = re.sub(r'\s*\*\s*', ' ', comment).strip()
        comment = re.sub(r'@\w+.*', '', comment).strip()
        if comment:
            return comment

    # Fall back to function name + class names
    # Convert camelCase to words
    words = re.sub(r'([A-Z])', r' \1', function_name).strip().lower()
    class_list = ", ".join(sorted(classes_used))
    return f"{words} using {class_list}"


def extract_workflows_from_source(
    source_file: SourceFile,
    known_classes: set[str],
    config: Config,
) -> list[Workflow]:
    """Extract all Ghidra API workflows from a single Java source file.

    Args:
        source_file: The source file to process.
        known_classes: Set of known Ghidra class names (simple names).
        config: Application configuration.

    Returns:
        List of Workflow objects, one per function that contains Ghidra API calls.
    """
    try:
        source = source_file.path.read_bytes()
    except (OSError, IOError) as e:
        logger.warning("Could not read %s: %s", source_file.path, e)
        return []

    tree = parse_java(source)
    imports = find_imports(tree, source)
    superclass = find_superclass(tree, source)

    # Determine which imported classes are Ghidra types
    ghidra_type_map: dict[str, str] = {}  # simple_name -> fqn
    for simple_name, fqn in imports.items():
        if _is_ghidra_import(fqn):
            ghidra_type_map[simple_name] = fqn

    # Check if this class extends GhidraScript
    is_ghidra_script = superclass in ("GhidraScript", "GhidraHeadlessScript")

    method_bodies = find_method_bodies(tree, source)
    workflows = []

    for method_name, body_node in method_bodies:
        workflow = _extract_workflow_from_method(
            method_name=method_name,
            body_node=body_node,
            source=source,
            ghidra_type_map=ghidra_type_map,
            known_classes=known_classes,
            is_ghidra_script=is_ghidra_script,
            config=config,
            source_file=source_file,
        )
        if workflow and len(workflow.calls) >= 2:
            workflows.append(workflow)

    return workflows


def _extract_workflow_from_method(
    method_name: str,
    body_node: Node,
    source: bytes,
    ghidra_type_map: dict[str, str],
    known_classes: set[str],
    is_ghidra_script: bool,
    config: Config,
    source_file: SourceFile,
) -> Workflow | None:
    """Extract a workflow from a single method body."""
    # Track variables assigned from Ghidra API calls
    # var_name -> (class_name, call_index)
    # call_index of -1 means "pre-existing" (parameter or field, not from a call)
    var_tracker: dict[str, tuple[str, int]] = {}

    # Seed var_tracker with method parameters whose type is a known Ghidra class
    method_node = body_node.parent
    if method_node is not None:
        params_node = method_node.child_by_field_name("parameters")
        if params_node is not None:
            for param in params_node.named_children:
                if param.type == "formal_parameter":
                    type_node = param.child_by_field_name("type")
                    name_node = param.child_by_field_name("name")
                    if type_node and name_node:
                        type_name = get_node_text(type_node, source)
                        param_name = get_node_text(name_node, source)
                        if type_name in ghidra_type_map or type_name in known_classes:
                            var_tracker[param_name] = (type_name, -1)

    # Seed GhidraScript well-known fields (e.g., currentProgram -> Program)
    if is_ghidra_script:
        for field_name, field_type in _GHIDRA_SCRIPT_FIELDS.items():
            var_tracker[field_name] = (field_type, -1)

    # Collect all API calls in source order
    calls: list[ApiCall] = []
    data_flow: list[DataFlowEdge] = []
    ghidra_classes: set[str] = set()

    # Walk all nodes in the method body
    all_nodes = _walk_nodes_by_offset(body_node)

    for node in all_nodes:
        call = None

        if node.type == "object_creation_expression":
            call = _process_object_creation(
                node, source, ghidra_type_map, known_classes
            )
        elif node.type == "method_invocation":
            call = _process_method_invocation(
                node, source, ghidra_type_map, known_classes,
                var_tracker, is_ghidra_script, config,
            )

        if call is None:
            continue

        call_index = len(calls)
        calls.append(call)
        ghidra_classes.add(call.class_name)

        # Track variable assignment: check if this node is the value
        # of a variable declaration or assignment
        _track_variable_assignment(
            node, source, call, call_index, var_tracker,
            ghidra_type_map, known_classes,
        )

        # Build data flow edges
        _build_data_flow_edges(
            call, call_index, var_tracker, data_flow
        )

    if not calls:
        return None

    # Get the full method source snippet (including any preceding comment)
    snippet_start = body_node.parent.start_byte if body_node.parent else body_node.start_byte
    snippet_end = body_node.end_byte
    source_snippet = source[snippet_start:snippet_end].decode("utf-8", errors="replace")

    description = _generate_description(method_name, ghidra_classes, source_snippet)

    return Workflow(
        calls=calls,
        data_flow=data_flow,
        source_snippet=source_snippet,
        function_name=method_name,
        file_path=str(source_file.path),
        trust_level=source_file.trust_level,
        category=source_file.category,
        ghidra_classes_used=ghidra_classes,
        description=description,
    )


def _process_object_creation(
    node: Node,
    source: bytes,
    ghidra_type_map: dict[str, str],
    known_classes: set[str],
) -> ApiCall | None:
    """Process a `new ClassName(...)` expression."""
    type_node = node.child_by_field_name("type")
    args_node = node.child_by_field_name("arguments")
    if type_node is None:
        return None

    class_name = get_node_text(type_node, source)
    # Strip generic type parameters
    if "<" in class_name:
        class_name = class_name[: class_name.index("<")]

    if class_name not in ghidra_type_map and class_name not in known_classes:
        return None

    arg_vars = _extract_argument_identifiers(args_node, source) if args_node else []

    return ApiCall(
        class_name=class_name,
        method_name="<init>",
        full_text=get_node_text(node, source),
        line_number=node.start_point[0] + 1,
        byte_offset=node.start_byte,
        receiver_var=None,
        argument_vars=arg_vars,
    )


def _process_method_invocation(
    node: Node,
    source: bytes,
    ghidra_type_map: dict[str, str],
    known_classes: set[str],
    var_tracker: dict[str, tuple[str, int]],
    is_ghidra_script: bool,
    config: Config,
) -> ApiCall | None:
    """Process an `obj.method(args)` expression."""
    name_node = node.child_by_field_name("name")
    object_node = node.child_by_field_name("object")
    args_node = node.child_by_field_name("arguments")

    if name_node is None:
        return None

    method_name = get_node_text(name_node, source)

    # Case 1: Called on a tracked variable (e.g., ifc.openProgram())
    if object_node is not None:
        receiver_text = get_node_text(object_node, source)
        if receiver_text in var_tracker:
            class_name = var_tracker[receiver_text][0]
            arg_vars = _extract_argument_identifiers(args_node, source) if args_node else []
            return ApiCall(
                class_name=class_name,
                method_name=method_name,
                full_text=get_node_text(node, source),
                line_number=node.start_point[0] + 1,
                byte_offset=node.start_byte,
                receiver_var=receiver_text,
                argument_vars=arg_vars,
            )

        # Case 2: Called on a known Ghidra type (e.g., static method)
        if receiver_text in ghidra_type_map or receiver_text in known_classes:
            arg_vars = _extract_argument_identifiers(args_node, source) if args_node else []
            return ApiCall(
                class_name=receiver_text,
                method_name=method_name,
                full_text=get_node_text(node, source),
                line_number=node.start_point[0] + 1,
                byte_offset=node.start_byte,
                receiver_var=receiver_text,
                argument_vars=arg_vars,
            )

        # Case 3: Chained call (e.g., program.getListing().getFunctionAt())
        # The receiver might itself be a method invocation on a tracked var
        if object_node.type == "method_invocation":
            inner_obj = object_node.child_by_field_name("object")
            if inner_obj is not None:
                inner_text = get_node_text(inner_obj, source)
                if inner_text in var_tracker:
                    class_name = var_tracker[inner_text][0]
                    inner_method = object_node.child_by_field_name("name")
                    inner_method_name = get_node_text(inner_method, source) if inner_method else "?"
                    # We represent this as a call from the intermediate result
                    arg_vars = _extract_argument_identifiers(args_node, source) if args_node else []
                    return ApiCall(
                        class_name=class_name,
                        method_name=f"{inner_method_name}().{method_name}",
                        full_text=get_node_text(node, source),
                        line_number=node.start_point[0] + 1,
                        byte_offset=node.start_byte,
                        receiver_var=inner_text,
                        argument_vars=arg_vars,
                    )

    # Case 4: GhidraScript inherited method (no explicit receiver)
    if is_ghidra_script and object_node is None:
        if method_name in config.ghidra_script_methods:
            arg_vars = _extract_argument_identifiers(args_node, source) if args_node else []
            return ApiCall(
                class_name="GhidraScript",
                method_name=method_name,
                full_text=get_node_text(node, source),
                line_number=node.start_point[0] + 1,
                byte_offset=node.start_byte,
                receiver_var=None,
                argument_vars=arg_vars,
            )

    return None


def _track_variable_assignment(
    node: Node,
    source: bytes,
    call: ApiCall,
    call_index: int,
    var_tracker: dict[str, tuple[str, int]],
    ghidra_type_map: dict[str, str],
    known_classes: set[str],
) -> None:
    """Check if this call's result is assigned to a variable and track it."""
    parent = node.parent
    if parent is None:
        return

    # Case: variable_declarator → local_variable_declaration
    #   e.g., DecompileResults res = ifc.decompileFunction(func, 30, null);
    if parent.type == "variable_declarator":
        name_node = parent.child_by_field_name("name")
        if name_node:
            var_name = get_node_text(name_node, source)
            call.return_var = var_name

            # Use the declared type if it's a known Ghidra type,
            # otherwise fall back to the call's class_name
            tracked_class = call.class_name
            decl_node = parent.parent  # local_variable_declaration
            if decl_node and decl_node.type == "local_variable_declaration":
                type_node = decl_node.child_by_field_name("type")
                if type_node:
                    declared_type = get_node_text(type_node, source)
                    # Strip array brackets and generics
                    base_type = declared_type.rstrip("[]")
                    if "<" in base_type:
                        base_type = base_type[: base_type.index("<")]
                    if base_type in ghidra_type_map or base_type in known_classes:
                        tracked_class = base_type

            var_tracker[var_name] = (tracked_class, call_index)

    # Case: assignment_expression
    #   e.g., ifc = new DecompInterface();
    elif parent.type == "assignment_expression":
        left = parent.child_by_field_name("left")
        if left and left.type == "identifier":
            var_name = get_node_text(left, source)
            call.return_var = var_name
            var_tracker[var_name] = (call.class_name, call_index)


def _build_data_flow_edges(
    call: ApiCall,
    call_index: int,
    var_tracker: dict[str, tuple[str, int]],
    data_flow: list[DataFlowEdge],
) -> None:
    """Build data flow edges from tracked variables into this call."""
    # Check receiver
    if call.receiver_var and call.receiver_var in var_tracker:
        source_class, source_idx = var_tracker[call.receiver_var]
        # Don't self-reference; skip pre-existing params (index == -1)
        if source_idx != call_index and source_idx >= 0:
            data_flow.append(DataFlowEdge(
                source_call_index=source_idx,
                target_call_index=call_index,
                variable_name=call.receiver_var,
                role="receiver",
            ))

    # Check arguments
    for arg_var in call.argument_vars:
        if arg_var in var_tracker:
            source_class, source_idx = var_tracker[arg_var]
            if source_idx != call_index and source_idx >= 0:
                data_flow.append(DataFlowEdge(
                    source_call_index=source_idx,
                    target_call_index=call_index,
                    variable_name=arg_var,
                    role="argument",
                ))
