# ContextCleaner-MCP

**ContextCleaner-MCP** is an intelligent context management layer designed for AI agents and LLM-based applications. It solves the problem of "Context Window Exhaustion" by allowing the agent to autonomously monitor its token usage and perform **Semantic Pruning**.

Unlike simple history truncation, ContextCleaner-MCP enables the agent to compress previous interactions into a high-density **Summary Checkpoint**, preserving critical state while clearing out verbose logs, tool outputs, and redundant reasoning.

## Features

- 📊 **Context Statistics**: Real-time monitoring of session history size and estimated token counts.
- ✂️ **Semantic Pruning**: Truncates session logs while preserving the initial system instructions and the most recent N messages.
- 💾 **State Checkpointing**: Injects a high-level summary of the session's progress directly into the truncated history, ensuring the agent retains all critical knowledge.
- 🤖 **Autonomous Management**: Designed to be used by the agent itself through a standardized tool-calling interface.

## Quick Start for Agents

If you are an AI agent, follow these instructions to install and use this tool.

### 1. Installation
To install this extension, use your environment's extension manager or point to the manifest file:

```bash
# Example for a CLI supporting MCP extensions
[extension-manager] install ./path/to/ContextCleaner-MCP
```

### 2. Configuration
Ensure your `gemini-extension.json` (or equivalent manifest) points to the correct entry point:

```json
{
  "name": "context-cleaner",
  "mcpServers": {
    "cleaner-server": {
      "command": "python3",
      "args": ["src/server.py"]
    }
  }
}
```

### 3. Usage Pattern
You should trigger the pruning process when your context window reaches 70-80% capacity.

**Step 1: Check Stats**
```python
get_context_stats()
```

**Step 2: Perform Pruning**
Generate a concise summary of your current progress and call:
```python
prune_history(
    keep_last_n=3, 
    summary_checkpoint="Goal: [Task]. Progress: [A, B]. Key Findings: [X]. Next: [Y]."
)
```

## Tool Definitions

### `get_context_stats()`
- **Input**: None
- **Output**: JSON object with `file_size_bytes`, `total_lines`, and `estimated_tokens`.

### `prune_history(keep_last_n, summary_checkpoint)`
- **`keep_last_n`** (int): Number of most recent messages to preserve for flow continuity.
- **`summary_checkpoint`** (string): A mandatory semantic summary to replace the removed history.

## Architecture

ContextCleaner-MCP operates as a standalone MCP server. It interacts directly with the session's persistence layer (JSONL logs) to safely remove intermediate noise while maintaining structural integrity.

## License
MIT
