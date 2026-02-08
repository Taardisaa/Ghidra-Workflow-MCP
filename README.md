# Ghidra Workflow MCP

An MCP server that helps LLMs write correct Ghidra scripts by providing **API workflow retrieval** — not just individual class docs, but the correct **call sequences** extracted from real Ghidra source code.

## The Problem

LLMs frequently get Ghidra API call sequences wrong. Decompiling a function isn't a single API call — it requires constructing a `DecompInterface`, calling `openProgram()`, obtaining a `Function`, invoking `decompileFunction()`, checking `decompileCompleted()`, and calling `dispose()`. Miss any step and the script silently fails.

This tool automatically extracts these workflow patterns from Ghidra's own source code, indexes them, and serves them via MCP so any LLM can query them.

## MCP Tools

| Tool | Purpose | Input |
|------|---------|-------|
| `get_workflows` | Find API call sequences for a task | Natural-language task description |
| `get_api_doc` | Look up a class or method (fuzzy match) | Class/method name or keyword |
| `list_related_apis` | Find co-occurring APIs | Class name |

### Example

```
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

```bash
# Clone and install
git clone https://github.com/your-username/Ghidra-Document-Retrieval.git
cd Ghidra-Document-Retrieval
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

## Usage

### 1. Build the index

Point to a local Ghidra source tree:

```bash
.venv/bin/ghidra-workflow-mcp build-index --ghidra-path /path/to/ghidra
```

Or let it clone Ghidra automatically:

```bash
.venv/bin/ghidra-workflow-mcp build-index
```

### 2. Test queries

```bash
.venv/bin/ghidra-workflow-mcp inspect "decompile a function"
.venv/bin/ghidra-workflow-mcp inspect "cross references to an address"
```

### 3. Run as MCP server

```bash
.venv/bin/ghidra-workflow-mcp serve
```

### Claude Code

Add the MCP server via the CLI:

```bash
claude mcp add ghidra-workflow /path/to/Ghidra-Document-Retrieval/.venv/bin/ghidra-workflow-mcp -- serve
```

Or create a `.mcp.json` file in the project root:

```json
{
  "mcpServers": {
    "ghidra-workflow": {
      "command": "/path/to/Ghidra-Document-Retrieval/.venv/bin/ghidra-workflow-mcp",
      "args": ["serve"]
    }
  }
}
```

### Claude Desktop

Add to `~/.config/Claude/claude_desktop_config.json` (Linux), `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS), or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "ghidra-workflow": {
      "command": "/path/to/Ghidra-Document-Retrieval/.venv/bin/ghidra-workflow-mcp",
      "args": ["serve"]
    }
  }
}
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

## License

MIT
