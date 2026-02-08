# Ghidra MCP API Documentation Retrieval Tool

## Motivation

Writing *semantically correct* scripts for decompiler backends—especially Ghidra—is unnecessarily painful. The difficulty is not syntax, but **API choreography**: knowing which objects to create, in what order to call them, what implicit state must be initialized, and what cleanup is required.

For example, decompiling a function is not a single API call. It requires constructing a `DecompInterface`, calling `openProgram()`, obtaining a `Function` from the `Listing`, invoking `decompileFunction()`, checking `decompileCompleted()`, and finally calling `dispose()`. **Miss any step and the script silently fails or leaks resources.** This choreography is undocumented in any single place.

Current LLM-based tooling struggles here because:
- Ghidra's APIs are large, Java-centric, and version-sensitive
- LLMs frequently hallucinate method names or misuse calling patterns
- **Even when LLMs get individual API names right, they get the call sequence wrong**
- Existing Ghidra MCP tools focus on *executing analysis*, not *explaining API workflows*

The result: even experienced reverse engineers spend excessive time debugging scripts that are *almost* correct.

This project proposes a **lightweight MCP (Model Context Protocol) tool** that provides **workflow-level API guidance for Ghidra**, designed to plug directly into existing AI coding tools and agents.

---

## Problem Statement

> There is currently no MCP-compatible tool that helps LLMs (or humans) retrieve **correct, real-world API call sequences** for Ghidra scripting tasks.

The core problem is not "what does `DecompInterface` do?" — it's **"how do I wire `DecompInterface`, `Program`, `Function`, `DecompileResults`, and `HighFunction` together to actually decompile something?"**

Specifically missing:
- **Workflow-level documentation**: ordered call chains showing how APIs interoperate
- **Real code examples**: extracted from working code, not hand-written
- **Task-oriented entry points**: search by what you want to accomplish, not by class name you may not know
- A lightweight, tool-only interface (no heavy agent pipeline)

---

## Non-Goals

This project explicitly does **not** aim to:
- Replace Ghidra scripting or analysis engines
- Perform binary analysis itself
- Compete with full agent systems like GhidraMCP (execution-focused)
- Build a complex multi-agent orchestration framework
- Hand-curate a documentation database

The focus is **automated workflow extraction + retrieval**, not execution or manual curation.

---

## Key Insight

Existing tools fall into two categories:

1. **Execution MCPs** (e.g., GhidraMCP):
   - Decompile, rename symbols, query functions
   - Don't explain *how* or *why*

2. **Generic doc retrievers** (e.g., Context7):
   - Library/framework documentation
   - Return individual class/method docs — not **call sequences**

**Neither addresses the real problem: API choreography.**

Individual API documentation already exists in Javadoc. What doesn't exist is a way to ask *"how do I accomplish task X?"* and get back a **real, working call chain** extracted from actual code.

This project fills that gap.

---

## Proposed Solution

A **Ghidra API Workflow Retrieval MCP Server** that automatically extracts API call sequences from real Ghidra code and exposes them as retrieval tools for LLMs and IDEs.

### Design Principles

- **Workflows first**: The primary unit is a *call chain*, not an individual class doc
- **Automated extraction**: Workflows are mined from real code, not hand-written
- **Lightweight**: MCP-only, no heavy orchestration
- **Composable**: Works alongside existing MCPs (GhidraMCP, IDA MCPs, etc.)
- **Semantics-first**: Focus on *correct usage patterns*, not just signatures

---

## Core Capabilities (MVP)

### 1. Workflow Retrieval (Primary Interface)

```text
get_workflows("decompile a function to C code")
get_workflows("cross-references to an address")
get_workflows("rename all functions matching a pattern")
```

Accepts a natural-language task description. Returns **ranked workflow matches**, each containing:
- Ordered API calls with data-flow dependencies
- The actual source snippet demonstrating the workflow
- Javadoc fragments for each API in the chain
- Annotations: what breaks if a step is skipped

Example output (top result, fully expanded):
```
Workflow: Decompile a function
Source: Ghidra/Features/Decompiler/src/test/...

1. DecompInterface ifc = new DecompInterface()
2. ifc.openProgram(currentProgram)              ← required, often forgotten
3. Function func = listing.getFunctionAt(addr)
4. DecompileResults res = ifc.decompileFunction(func, timeout, monitor)
5. if (!res.decompileCompleted()) → handle error ← often skipped
6. HighFunction hf = res.getHighFunction()       ← for pcode
7. ClangTokenGroup markup = res.getCCodeMarkup()  ← for C output
8. ifc.dispose()                                  ← resource leak if omitted
```

This is the tool an LLM calls **first** when generating a Ghidra script.

---

### 2. API Documentation Lookup (Secondary Drill-Down)

```text
get_api_doc("DecompInterface")
get_api_doc("Function")
get_api_doc("decompile")
```

Supports **fuzzy and partial matching** — no fully-qualified import path required:
- Short class name → returns candidates across packages with disambiguation
- Keyword search → surfaces related classes and methods
- Fully-qualified path → precise lookup (optional, not required)

Returns:
- Class / method signatures
- JavaDoc excerpts
- Parameter semantics
- Links to workflows that use this API

---

### 3. Related API Discovery

```text
list_related_apis("DecompInterface")
```

Returns:
- APIs commonly used alongside the queried one (co-occurrence in real code)
- Upstream dependencies (what you need before calling this)
- Downstream consumers (what typically follows)

---

## Data Pipeline

The core of this project is an **automated extraction pipeline**, not a hand-curated database.

### Data Sources (Ranked by Trust)

| Source | Trust | Content |
|--------|-------|---------|
| **Ghidra source code** (Features/*/src/main/java) | Highest | How Ghidra's own developers use the APIs internally |
| **Ghidra test suite** (Features/*/src/test) | Highest | Step-by-step workflow demonstrations with assertions |
| **Ghidra example scripts** (Extensions/sample, ghidra_scripts) | High | Purpose-built usage examples |
| **Ghidra Javadoc** | High | Authoritative signatures and descriptions |
| **Established community repos** (high-star, known-good) | Medium | Real-world usage patterns, broader coverage |
| **General GitHub Ghidra scripts** | Lower | Volume and coverage, ranked lower in results |

Source quality ranking ensures trusted code surfaces first in retrieval results.

### Approach A: Static Extraction Pipeline (Current Implementation)

Pre-computes workflow call chains at index time. Fast and cheap at query time — no LLM calls needed.

```
[1. Collect]  Fetch code from Ghidra source, GitHub (code search API), known repos
      ↓
[2. Parse]    Tree-sitter (Java/Python) → AST
      ↓
[3. Extract]  Identify ghidra.* API calls per function/script
              Record call order + data flow (variable assignments linking calls)
              Build call-chain graphs: call_A --output_feeds--> call_B
      ↓
[4. Index]    Store call chains + source snippets + Javadoc fragments
              Embed with semantic vectors for natural-language search
      ↓
[5. Serve]    MCP server retrieves relevant workflows at query time
```

**What "Extract" produces** for each code sample:
- **Call chain**: ordered list of `ghidra.*` API calls with data-flow edges
- **Source snippet**: the original code (attributed)
- **Context**: surrounding comments, function name, file path
- **Javadoc links**: each API call linked to its documentation

These are stored as lightweight graph structures, not prose.

### Approach B: RAG with Agent Synthesis (Future Alternative)

Instead of pre-computing structured call chains, this approach uses an LLM at query time to synthesize workflow explanations from retrieved code.

```
[1. Collect]  Fetch code from Ghidra source, GitHub, known repos
      ↓
[2. Chunk]    Split into function/script-level units
      ↓
[3. Embed]    Semantic vectors for each chunk (raw code + metadata)
      ↓
[4. Query]    Retrieve top-k chunks matching user query
      ↓
[5. Agent]    LLM reads retrieved code, synthesizes workflow explanation
      ↓
[6. Return]   MCP response with call chain + source attribution
```

**Tradeoffs vs. Approach A:**

| | Static Extraction | RAG with Agent |
|---|---|---|
| Query latency | Fast (index lookup only) | Slower (LLM call per query) |
| Query cost | Free (no API calls) | LLM API cost per query |
| Flexibility | Fixed to pre-extracted patterns | Can answer unanticipated questions |
| Index complexity | Requires tree-sitter + call chain extraction | Simpler — just embed raw code chunks |
| Output quality | Structured but rigid | Adaptive, can explain *why* each step matters |

The MCP server can support both approaches behind the same tool interface — the user doesn't need to know which pipeline produced the answer.

---

## MCP Interface Design

The server exposes **pure retrieval tools**:

| Tool | Role | Input |
|------|------|-------|
| `get_workflows` | Primary — ranked workflow call chains for a task | Natural-language task description |
| `get_api_doc` | Drill-down — class/method documentation | Fuzzy class/method name or keyword |
| `list_related_apis` | Exploration — co-occurring APIs | Class/method name |

No binary analysis state is required. All tools are stateless and read-only.

---

## Why MCP?

- Works with Claude, GPT, Cursor, Continue, etc.
- Zero lock-in
- No agent learning curve
- Easy adoption for researchers and practitioners

Users can simply *add the MCP server* and immediately get better Ghidra scripts.

---

## Relationship to Existing Projects

| Project | Focus | Difference |
|---------|-------|------------|
| GhidraMCP | Analysis execution | Ours provides the *knowledge* to write correct scripts |
| Context7 | General library docs | Ours extracts *workflow call chains*, not just class docs |
| ghidra_bridge / PyGhidra | API access | Ours explains *how to wire APIs together* |
| Javadoc | Individual class/method docs | Ours provides *task-oriented sequences* across classes |

This tool is **complementary**, not competitive.

---

## Expected Impact

- Dramatically reduces hallucinated Ghidra API usage by grounding LLMs in **real code**
- Solves the "call A then call B" problem — correct sequencing, not just correct names
- Faster script prototyping with workflow-level examples
- Lower barrier for new Ghidra users
- Strong foundation for future agent-based RE systems

---

## Future Extensions (Optional)

- Cross-decompiler workflow abstraction (IDA / Binary Ninja / angr)
- Typed API schemas (for validation)
- Call-sequence linting: validate a script's API call order against known-good workflows
- IDE integration (hover docs, inline workflow suggestions)
- Context-aware retrieval: accept a list of types present in the current binary to refine results

---

## Summary

This project proposes a **lightweight MCP tool for Ghidra API workflow retrieval**, addressing a real and unsolved pain point in reverse engineering automation.

The key shift from traditional documentation tools: **workflows (ordered call chains) are the primary unit**, not individual class docs. These workflows are **automatically extracted from real code** — Ghidra's own source, tests, examples, and community scripts — not hand-curated.

Rather than building another complex agent pipeline, it focuses on *giving existing AI tools the correct API choreography* when interacting with Ghidra.

**Automated extraction. Workflow-first retrieval. High leverage.**
