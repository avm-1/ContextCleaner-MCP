# ContextCleaner-MCP v2.0 — Selective Pruning

**ContextCleaner-MCP** is a context-management server for the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) that implements **selective pruning** of session messages.

Unlike naive truncation ("keep the last N messages"), this server lets an agent **mark specific messages as irrelevant** and delete only those, preserving critically important context.

## The Problem

In long sessions, agents generate a lot of intermediate data:
- Large tool outputs: JSON, CSV, HTML, logs
- Intermediate reasoning steps that have become obsolete
- Duplicate requests

Simple "keep last N" truncation risks losing:
- Initial system instructions
- Important user clarifications from the middle of the conversation
- Key agent decisions

## Solution: Selective Pruning

The agent (or client) marks messages with a special flag in `metadata`:

```json
{
  "id": "tool-001",
  "role": "tool",
  "type": "tool_output",
  "content": "... massive JSON output ...",
  "metadata": {
    "prune": true,
    "prune_reason": "intermediate data",
    "pruned_at": "2026-05-26T12:00:00Z"
  }
}
```

The MCP server finds all marked messages and safely removes them:
- Creates a backup before any modification
- Uses atomic write (write to temp file + rename)
- Returns token savings statistics

## Tools

### `get_context_stats()`
Returns session statistics, including the number of marked messages and potential token savings.

```json
{
  "file_path": "...",
  "total_messages": 14,
  "total_tokens": 1623,
  "marked_for_pruning": 8,
  "marked_tokens": 969,
  "potential_savings_percent": 59.7
}
```

### `mark_for_pruning(criteria)`
Marks messages for deletion by criteria:
- `ids`: array of message IDs
- `types`: array of types (`tool_output`, `reasoning`, ...)
- `roles`: array of roles (`tool`, `assistant`, ...)
- `content_pattern`: substring to search in content
- `reason`: reason for marking (stored in metadata)

```json
{
  "ids": ["tool-001", "tool-002"],
  "types": ["tool_output", "reasoning"],
  "reason": "heavy intermediate data"
}
```

### `prune_marked()`
Deletes all messages with `metadata.prune = true`.
Automatically creates a `.backup`.

Returns detailed statistics:
```json
{
  "status": "success",
  "pruned_count": 8,
  "tokens_saved": 969,
  "savings_percent": 59.7,
  "backup_created": true
}
```

### `restore_backup()`
Restores the session from the latest backup.

### `list_messages(show_pruned_only)`
Returns a list of messages with their prune status and estimated token count.

## Quick Start

```bash
# Set the directory with .jsonl sessions
export SESSION_DIR="./tmp/chats"

# Start the server
python src/server.py
```

The server reads requests from stdin and writes responses to stdout in JSON-RPC 2.0 format.

## Usage Example

**Session: CSV analysis + visualization**

| ID | Type | Content | Decision |
|----|------|---------|----------|
| `sys-001` | system | Instructions | Keep |
| `user-001` | user | Request | Keep |
| `think-001` | reasoning | Intermediate thought | Mark |
| `tool-001` | tool_output | `head` CSV (50000 rows) | Mark |
| `think-002` | reasoning | Intermediate thought | Mark |
| `tool-002` | tool_output | `describe()` output | Mark |
| `assistant-001` | final | Final script + explanation | Keep |
| `user-002` | user | Clarification | Keep |
| `think-004` | reasoning | Intermediate thought | Mark |
| `tool-004` | tool_output | Correlation matrix | Mark |
| `assistant-002` | final | Final answer | Keep |

**Result:**
- Before prune: 14 messages, 1623 tokens
- After prune: 6 messages, 654 tokens
- **Savings: 969 tokens (59.7%)**
- All critical messages preserved

## Comparison with Truncation: Real Case (HTML Chess)

A session of developing interactive HTML chess contained 18 messages with heavy tool outputs (docs, logs, base64 screenshots), reasoning steps, and two versions of the final code.

### What truncation keeps (v1.0, keep_last_n=5)

| Kept | Lost | Problem |
|------|------|---------|
| system prompt | Kept | — |
| checkpoint summary | Kept | Generic phrase without details |
| user-003 (add highlight) | Lost | Agent doesn't know the original request |
| **think-005** (reasoning) | Lost | **Junk kept** |
| **tool-005** (base64 image) | Lost | **Junk kept** |
| assistant-003 (patch) | Lost | Full code v1 lost |
| user-004 (perfect!) | Lost | — |

**Result:** the agent sees only "add highlight" patch, but:
- Doesn't know what it was creating (no `user-001`)
- Doesn't have the full code (`assistant-002` lost)
- Wastes tokens on meaningless reasoning and base64 image

### What selective pruning keeps

| Kept | Lost |
|------|------|
| system prompt | Kept |
| user-001, user-002, user-003, user-004 | All requirements kept |
| assistant-002 (full code v1) | Kept |
| assistant-003 (patch v2) | Kept |

**Junk fully removed:** 11 messages (reasoning, tool outputs, intermediate code)

### Final Comparison

| Metric | Selective | Truncation |
|--------|-----------|------------|
| Messages remaining | 7 | 7 |
| Token savings | **79%** (2512 tokens) | 58% (1848 tokens) |
| Critical messages preserved | **7/7** | 4/7 |
| Junk remaining | **0** | 2 (reasoning + base64) |
| Agent can continue work | **Yes** | No |

## Safety

- **Backups:** `.backup` created before any modification
- **Atomic write:** Write to temp file + `shutil.move`
- **JSON validation:** Corrupted lines don't crash the session
- **Idempotency:** Repeated `prune_marked` is safe (no marked messages = no-op)

## Architecture

```
+-------------+     stdin/stdout      +---------------------+
|  MCP Client |  <---------------->   |  ContextCleaner-MCP |
|  (Agent/IDE)|      JSON-RPC 2.0     |     src/server.py   |
+-------------+                       +---------------------+
                                              |
                                              v
                                       +--------------+
                                       | SessionManager|
                                       | - read/write  |
                                       | - mark/prune  |
                                       | - backup      |
                                       +--------------+
                                              |
                                              v
                                       +--------------+
                                       | *.jsonl file |
                                       |  session     |
                                       +--------------+
```

## Testing

```bash
# Basic selective pruning tests
python test_selective_prune.py

# Comparison test: selective vs truncation (chess)
python test_chess_comparison.py

# Comparison with normal LLM workflow (tetris)
python test_tetris_comparison.py

# Real agent with auto-cleanup (without Kimi CLI)
python agent_client.py

# Real tests via Kimi CLI:
# cd test-chess-without-mcp && kimi --print --prompt "..."
# cd test-chess-with-mcp && kimi --print --prompt "..."
```

Tests verify:
1. Marking by type and ID
2. Token counting and savings
3. Deleting only marked messages
4. Preserving critical messages
5. Backup and restore correctness
6. **Context quality comparison** selective pruning vs truncation

## Example 2: Tetris Development (Comparison with Normal LLM Workflow)

A session of developing a full Tetris: 26 messages, 5 iterations, Canvas API, Web Audio, animations.

### RAW (normal work without cleanup)
- **26 messages, 4240 tokens**
- Quality: 100% (everything in place)
- Problem: 71% of tokens are junk (reasoning, tool outputs, intermediate code)
- In a long session context overflows, each request gets more expensive

### Selective Pruning
- **10 messages, 1228 tokens**
- Savings: **71% of tokens (3012)**
- Quality: **100%** — all requirements and all code versions preserved
- Junk: **0**

### Truncation (keep_last_n=5)
- **7 messages, 914 tokens**
- Quality: **40%** — original requirements and final code v1 lost
- Junk: **2** (reasoning + Web Audio test)
- Agent cannot add a new piece or touch controls

### Modification Capability

| Task | RAW | Selective | Truncation |
|------|-----|-----------|------------|
| Add piece | Yes | Yes | No |
| Change colors | Yes | Yes | No |
| Touch controls | Yes | Yes | No |
| Remove music | Yes | Yes | Yes |
| Change speed | Yes | Yes | No |

### Economic Benefit

For 100 requests in a long session: **301,200 tokens saved** (~$0.90)
When scaling to thousands of requests, savings become substantial.

## Example 3: Chess Development via Kimi CLI (Real Tests)

Direct comparison of two approaches using real Kimi Code CLI.

### Without MCP (normal work)

```bash
cd test-chess-without-mcp
kimi --print --prompt "Create a chess board in HTML..."
kimi --print --prompt "Update chess.html to add interactivity..."
```

**Result:**
- `chess.html`: **8202 bytes** (full interactive chess)
- Session: **9 messages, 345 tokens**
- All junk preserved: reasoning, tool outputs, intermediate code

### With MCP (auto-cleanup)

```bash
cd test-chess-with-mcp
kimi --print --prompt "Create a chess board... After finishing, use context-cleaner MCP to clean up intermediate steps."
```

**Result:**
- `chess.html`: **6049 bytes** (basic + interactive version)
- Session after prune: **4 messages, 72 tokens**
- **Savings: 79% of tokens (273 of 345)**

### Context Comparison

| Parameter | WITHOUT MCP | WITH MCP |
|-----------|-------------|----------|
| Messages in context | 9 | 4 |
| Tokens | 345 | **72** |
| Junk (reasoning/tool) | 5 | **0** |
| Old code versions | Preserved | **Removed** |
| Backup | No | Yes |

### What Remains After MCP Cleanup

| ID | Type | Status |
|----|------|--------|
| user-001 | user | Preserved |
| user-002 | user | Preserved |
| assistant-002 | final | Preserved |

### What Was Removed

| ID | Type | Reason |
|----|------|--------|
| think-001 | reasoning | Intermediate thought |
| tool-001 | tool_output | Validator output |
| assistant-001 | intermediate | Outdated code v1 |
| think-002 | reasoning | Intermediate thought |
| tool-002 | tool_output | Linter output |

### How It Works in Kimi CLI

1. MCP server is configured in `~/.kimi/mcp.json`
2. When `kimi` starts, it automatically connects to `context-cleaner`
3. Kimi sees 5 tools and can call them by name
4. After code generation, Kimi calls `mark_for_pruning` + `prune_marked`
5. Context is cleaned automatically

### Connection Confirmation

```bash
$ kimi mcp list
  context-cleaner (stdio): python server.py
```

```bash
$ kimi mcp test context-cleaner
  Testing connection to 'context-cleaner'...
  Connected successfully
  Tools: get_context_stats, mark_for_pruning, prune_marked, restore_backup, list_messages
```

## Requirements

- Python 3.10+
- No external dependencies (stdlib only)

## License

MIT
