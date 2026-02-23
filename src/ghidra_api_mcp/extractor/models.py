"""Core data models for workflow extraction."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class TrustLevel(Enum):
    HIGHEST = "highest"  # test code, example scripts
    HIGH = "high"  # main Ghidra source
    MEDIUM = "medium"  # community code


@dataclass
class SourceFile:
    """A Java source file to be processed."""

    path: Path
    trust_level: TrustLevel
    category: str  # "test", "example_script", "main_source"


@dataclass
class ApiCall:
    """A single Ghidra API call (method invocation or constructor)."""

    class_name: str  # e.g., "DecompInterface"
    method_name: str  # e.g., "openProgram" or "<init>" for constructors
    full_text: str  # e.g., "ifc.openProgram(program)"
    line_number: int
    byte_offset: int  # position in source for ordering
    return_var: str | None = None  # variable name this result is assigned to
    receiver_var: str | None = None  # variable this is called on (None for constructors)
    argument_vars: list[str] = field(default_factory=list)


@dataclass
class DataFlowEdge:
    """Links one API call's output to another's input."""

    source_call_index: int  # index into Workflow.calls
    target_call_index: int  # index into Workflow.calls
    variable_name: str  # the variable connecting them
    role: str  # "receiver" or "argument"


@dataclass
class Workflow:
    """A complete API workflow extracted from a single function."""

    calls: list[ApiCall]
    data_flow: list[DataFlowEdge]
    source_snippet: str
    function_name: str
    file_path: str
    trust_level: TrustLevel
    category: str
    ghidra_classes_used: set[str] = field(default_factory=set)
    description: str = ""

    @property
    def id(self) -> str:
        """Unique identifier derived from source location and content."""
        key = f"{self.file_path}:{self.function_name}:{len(self.calls)}"
        return hashlib.sha256(key.encode()).hexdigest()[:16]

    def to_display_text(self) -> str:
        """Format as the ordered step-by-step display shown to the user."""
        lines = [f"Workflow: {self.function_name}"]
        lines.append(f"Source: {self.file_path}")
        lines.append("")
        for i, call in enumerate(self.calls):
            if call.method_name == "<init>":
                step = f"{i + 1}. new {call.class_name}()"
            else:
                receiver = f"{call.receiver_var}." if call.receiver_var else ""
                step = f"{i + 1}. {receiver}{call.method_name}(...)"

            # Annotate with data flow info
            incoming = [e for e in self.data_flow if e.target_call_index == i]
            if incoming:
                deps = ", ".join(
                    f"uses {e.variable_name} from step {e.source_call_index + 1}"
                    for e in incoming
                )
                step += f"  [{deps}]"
            lines.append(step)
        return "\n".join(lines)

    def to_embedding_text(self) -> str:
        """Generate text used for semantic embedding/search."""
        class_list = ", ".join(sorted(self.ghidra_classes_used))
        call_list = " -> ".join(
            f"{c.class_name}.{c.method_name}" for c in self.calls
        )
        parts = []
        if self.description:
            parts.append(f"Ghidra workflow: {self.description}.")
        parts.append(f"Classes: {class_list}.")
        parts.append(f"Call chain: {call_list}.")
        parts.append(f"Source function: {self.function_name}")
        return " ".join(parts)
