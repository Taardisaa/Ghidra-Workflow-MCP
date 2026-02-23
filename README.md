# Ghidra-Script-Helper

A MCP tool that helps LLMs write correct Ghidra scripts by providing API-callflows extracted from Ghidra's own source code.

## Problem Statement

LLMs frequently get Ghidra API call sequences wrong. Decompiling a function isn't a single API call; it requires constructing a `DecompInterface`, calling `openProgram()`, obtaining a `Function`, invoking `decompileFunction()`, checking `decompileCompleted()`, and calling `dispose()`. Miss any step and the script silently fails.

This tool automatically extracts these workflow patterns from Ghidra's own source code, indexes them vis `chromadb`, and serves them via MCP so any agent tools can query them.

## MCP Tools

| Tool | Purpose | Input |
|------|---------|-------|
| `initialize_index` | Build the RAG database (run once before first use) | Optional path to local Ghidra source |
| `get_index_info` | Show Ghidra version, build timestamp, and record counts | — |
| `clear_index` | Delete the index (use before a clean rebuild) | — |
| `get_workflows` | Find API call sequences for a task | Natural-language task description |
| `get_api_doc` | Look up a class or method (fuzzy match) | Class/method name or keyword |
| `list_related_apis` | Find co-occurring APIs | Class name |

### Example

```
initialize_index()                                    # first-time setup; clones Ghidra automatically
initialize_index("/path/to/ghidra")                   # or point at a local Ghidra source tree

get_workflows("decompile a function to C code")
```

Returns:
```
Workflow: decompileFunction
Source: Ghidra/Features/Decompiler/src/test/...

1. new DecompInterface()
2. ifc.openProgram(...)       [uses ifc from step 1]
3. program.getListing().getFunctionAt(...)
4. ifc.decompileFunction(...) [uses func from step 3]
5. res.decompileCompleted()
6. res.getDecompiledFunction().getC()
7. ifc.dispose()
```

## Setup

### Quick start (from PyPI)

**1. Add the server to Claude Code:**

```bash
claude mcp add ghidra-workflow -- uvx ghidra-workflow-mcp
```

Or for Claude Desktop, add to your config file (`~/.config/Claude/claude_desktop_config.json` on Linux, `~/Library/Application Support/Claude/claude_desktop_config.json` on macOS, `%APPDATA%\Claude\claude_desktop_config.json` on Windows):

```json
{
  "mcpServers": {
    "ghidra-workflow": {
      "command": "uvx",
      "args": ["ghidra-workflow-mcp"]
    }
  }
}
```

**2. Build the index on first use:**

Call `initialize_index` from Claude — it will clone Ghidra automatically and build the RAG database (takes 10–30 minutes). Subsequent sessions reuse the built index.

### From source

```bash
git clone https://github.com/Taardisaa/Ghidra-Script-Helper.git
cd Ghidra-Script-Helper
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

**Add to Claude Code:**

```bash
claude mcp add ghidra-workflow -- uv run --directory /path/to/Ghidra-Script-Helper ghidra-workflow-mcp
```

**Or build the index offline first (CLI):**

```bash
# Auto-clone Ghidra
ghidra-workflow-mcp-admin build-index

# Or point at a local Ghidra source tree
ghidra-workflow-mcp-admin build-index --ghidra-path /path/to/ghidra
```

**Inspect / test without MCP:**

```bash
ghidra-workflow-mcp-admin inspect info                               # get_index_info
ghidra-workflow-mcp-admin inspect workflows "decompile a function"   # get_workflows
ghidra-workflow-mcp-admin inspect api-doc DecompInterface            # get_api_doc
ghidra-workflow-mcp-admin inspect related DecompInterface            # list_related_apis
```

**Clear the index:**

```bash
ghidra-workflow-mcp-admin clear-index
```

## How It Works

```
[1. Collect]  Enumerate Java files from Ghidra source (tests, examples, main code)
      ↓
[2. Parse]    tree-sitter Java → AST
      ↓
[3. Extract]  Identify ghidra.* API calls per function
              Track variable assignments to build data-flow edges
              Build call-chain graphs: call_A --output_feeds--> call_B
      ↓
[4. Index]    Store call chains + source snippets in ChromaDB
              Embed with semantic vectors for natural-language search
      ↓
[5. Serve]    MCP server retrieves relevant workflows at query time
```

Data sources are ranked by trust: Ghidra's own tests and examples surface first, main source code second.

## Development

```bash
# Run tests
.venv/bin/pytest -v

# Lint
.venv/bin/ruff check src/ tests/
```

## Note

**Warnings when indexing chromadb**: The following error may appear during indexing:

```[W:onnxruntime:Default, device_discovery.cc:164 DiscoverDevicesForPlatform] GPU device discovery failed: device_discovery.cc:89 ReadFileContents Failed to open file: "/sys/class/drm/card0/device/vendor"```

This is expected. It will fallback to CPU embedding if GPU is unavailable.

## License

MIT
