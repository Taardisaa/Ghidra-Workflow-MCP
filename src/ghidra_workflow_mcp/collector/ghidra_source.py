"""Collect and enumerate Java source files from a Ghidra source tree."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from ghidra_workflow_mcp.config import Config
from ghidra_workflow_mcp.extractor.models import SourceFile, TrustLevel

logger = logging.getLogger(__name__)

TRUST_MAP = {
    "highest": TrustLevel.HIGHEST,
    "high": TrustLevel.HIGH,
    "medium": TrustLevel.MEDIUM,
}


def validate_ghidra_root(path: Path) -> bool:
    """Check that a path looks like a Ghidra source tree."""
    return (path / "Ghidra" / "Features").is_dir()


def clone_ghidra(config: Config, target: Path) -> Path:
    """Shallow-clone the Ghidra repo into target directory."""
    if target.exists() and validate_ghidra_root(target):
        logger.info("Ghidra source already exists at %s, skipping clone", target)
        return target

    logger.info("Cloning Ghidra repo (depth=%d) into %s ...", config.clone_depth, target)
    subprocess.run(
        [
            "git", "clone",
            "--depth", str(config.clone_depth),
            config.ghidra_clone_url,
            str(target),
        ],
        check=True,
    )
    return target


def enumerate_java_files(ghidra_root: Path, config: Config) -> list[SourceFile]:
    """Walk Ghidra source tree, return Java files ranked by trust.

    Files are deduplicated: if a file matches a higher-trust pattern,
    it won't be included again under a lower-trust pattern.
    """
    if not validate_ghidra_root(ghidra_root):
        raise ValueError(
            f"{ghidra_root} does not look like a Ghidra source tree "
            "(expected Ghidra/Features/ directory)"
        )

    seen_paths: set[Path] = set()
    results: list[SourceFile] = []

    for glob_pattern, trust_str, category in config.scan_dirs:
        trust = TRUST_MAP[trust_str]
        # Glob for Java files under this pattern
        pattern = glob_pattern.rstrip("/") + "/**/*.java"
        matched = sorted(ghidra_root.glob(pattern))

        for path in matched:
            resolved = path.resolve()
            if resolved in seen_paths:
                continue
            seen_paths.add(resolved)
            results.append(SourceFile(path=path, trust_level=trust, category=category))

    if config.max_files is not None:
        results = results[: config.max_files]

    logger.info(
        "Found %d Java files (%d highest, %d high, %d medium trust)",
        len(results),
        sum(1 for f in results if f.trust_level == TrustLevel.HIGHEST),
        sum(1 for f in results if f.trust_level == TrustLevel.HIGH),
        sum(1 for f in results if f.trust_level == TrustLevel.MEDIUM),
    )
    return results


def build_known_class_names(ghidra_root: Path) -> set[str]:
    """Build a set of known Ghidra class names from the source tree.

    Scans Java files under ghidra/ packages and extracts simple class names
    from file names. Used by the extractor to identify Ghidra types without
    full type resolution.
    """
    class_names: set[str] = set()
    ghidra_java_root = ghidra_root / "Ghidra"

    for java_file in ghidra_java_root.rglob("*.java"):
        # Only include files that are in a ghidra.* package path
        parts = java_file.parts
        try:
            ghidra_idx = parts.index("ghidra")
        except ValueError:
            continue
        # The file stem is the class name
        class_names.add(java_file.stem)

    logger.info("Built known class name set: %d classes", len(class_names))
    return class_names
