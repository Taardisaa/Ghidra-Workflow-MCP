# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install (dev mode)
.venv/bin/pip install -e ".[dev]"

# Run all tests
.venv/bin/pytest -v

# Run a single test file
.venv/bin/pytest tests/test_extractor.py -v

# Lint / format
.venv/bin/ruff check src/ tests/
.venv/bin/ruff format src/ tests/

# Build the ChromaDB index (requires Ghidra source)
ghidra-api-mcp-admin build-index --ghidra-path /path/to/ghidra
ghidra-api-mcp-admin build-index --max-files 100  # quick test run

# Query the index without MCP (mirrors MCP tools)
ghidra-api-mcp-admin inspect info
ghidra-api-mcp-admin inspect workflows "decompile a function"
ghidra-api-mcp-admin inspect api-doc DecompInterface
ghidra-api-mcp-admin inspect related DecompInterface

# Clear the index
ghidra-api-mcp-admin clear-index

# Run MCP server
python -m ghidra_api_mcp
```

## Architecture

**Pipeline** (offline, one-time):
```
Collect Java files  →  Parse AST (tree-sitter)  →  Extract call chains  →  Index (ChromaDB)
```

**Serve** (at query time via MCP):
```
Natural-language query  →  Semantic search ChromaDB  →  Return ranked workflow chains
```

**Source layout**: `src/ghidra_api_mcp/`

| Module | Role |
|--------|------|
| `server.py` | FastMCP server exposing 6 tools: `initialize_index`, `get_index_info`, `clear_index`, `get_workflows`, `get_api_doc`, `list_related_apis` |
| `pipeline.py` | Shared index-build pipeline used by both CLI and `initialize_index` MCP tool |
| `cli.py` | Click CLI: `build-index`, `clear-index`, `serve`, `inspect info\|workflows\|api-doc\|related` |
| `config.py` | Scan directories, trust levels, GhidraScript field definitions |
| `collector/ghidra_source.py` | Enumerate Java files; build known Ghidra class name set |
| `parser/java_parser.py` | tree-sitter Java → imports, method bodies, superclass |
| `extractor/call_chain.py` | Identify Ghidra API calls; build data-flow edges between calls |
| `extractor/models.py` | `ApiCall`, `DataFlowEdge`, `Workflow`, `TrustLevel` |
| `indexer/store.py` | Ingest workflows into ChromaDB (two collections: workflows + API classes) |
| `indexer/search.py` | `WorkflowSearcher`: semantic search with trust-level re-ranking |

**Trust levels** (affect result ranking): Ghidra tests/examples > Ghidra main source.

## Key Constraints

- **tree-sitter must stay at 0.21.3** — 0.23+ removed `Query.captures(node)`, breaking the parser.
- **ChromaDB quirks** (1.x): `delete_collection()` raises `NotFoundError` on missing collection (catch with `except Exception`); `$contains` is not a valid `where` filter — use semantic search + Python post-filter.
- **Variable type tracking in extractor**: seed `var_tracker` with method parameters and GhidraScript fields before walking a method body; use declared type for variable declarations, not the receiver's type; skip data-flow edges where `source_index == -1` (those are pre-existing params).
- **Venv** is at `.venv/` in project root.
- ChromaDB storage lives in `data/chroma_db/`.

## Tests

Test fixtures are small Java files in `tests/fixtures/` that cover the three main workflows (decompile, xref, GhidraScript). `tests/conftest.py` provides shared pytest fixtures.
