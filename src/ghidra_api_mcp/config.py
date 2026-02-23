"""Configuration for the Ghidra Workflow MCP server."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Config:
    ghidra_source_path: Path | None = None
    db_path: Path = field(default_factory=lambda: Path("data/chroma_db"))
    ghidra_clone_url: str = "https://github.com/NationalSecurityAgency/ghidra.git"
    clone_depth: int = 1
    max_files: int | None = None  # None = no limit
    search_results_default: int = 5

    # Directories to scan within Ghidra source, ordered by trust/priority.
    # Each tuple: (glob pattern relative to ghidra root, trust level, category)
    scan_dirs: list[tuple[str, str, str]] = field(default_factory=lambda: [
        ("Ghidra/Features/*/src/test/java/", "highest", "test"),
        ("Ghidra/Features/*/ghidra_scripts/", "highest", "example_script"),
        ("Ghidra/Features/*/src/main/java/ghidra/app/script/", "high", "main_source"),
        ("Ghidra/Features/*/src/main/java/", "high", "main_source"),
    ])

    # Known GhidraScript base class methods to treat as Ghidra API calls
    ghidra_script_methods: set[str] = field(default_factory=lambda: {
        "currentProgram", "currentAddress", "currentLocation",
        "currentSelection", "currentHighlight", "state",
        "println", "printerr", "askString", "askInt",
        "toAddr", "getFunctionAt", "getDataAt",
        "createFunction", "createLabel", "createBookmark",
        "monitor", "getMonitor",
    })
