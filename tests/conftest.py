"""Shared test fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture
def decompile_source() -> bytes:
    return (FIXTURES_DIR / "DecompileExample.java").read_bytes()


@pytest.fixture
def xref_source() -> bytes:
    return (FIXTURES_DIR / "XrefExample.java").read_bytes()


@pytest.fixture
def simple_script_source() -> bytes:
    return (FIXTURES_DIR / "SimpleScript.java").read_bytes()
