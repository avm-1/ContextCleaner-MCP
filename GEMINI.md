# Context Manager Extension

This extension allows the agent to monitor its own context usage and perform "Intelligent Pruning" when the session history becomes too large.

## When to use context management tools

1.  **Context Pressure:** If you notice that your performance is degrading, or if the `token_count` (if available) is exceeding 70-80% of the limit.
2.  **Task Completion:** After finishing a major sub-task, use `prune_history` to "offload" the verbose logs and keep only the final result as a checkpoint.
3.  **Long Sessions:** Every 10-15 turns, it is recommended to run `get_context_stats` to assess history size.

## Workflow: Intelligent Pruning

When the context needs to be cleared:

1.  **Reflect:** Analyze the current session history. Identify what information is critical (e.g., active task state, discovered credentials, architectural decisions) and what is noise (e.g., failed command attempts, large file reads already processed).
2.  **Summarize:** Create a concise "State Checkpoint" text. It should include:
    -   Goal of the session.
    -   Progress made so far.
    -   Critical technical facts discovered.
    -   Next steps.
3.  **Prune:** Call `prune_history(keep_last_n=3, summary_checkpoint="...")`.
    -   This tool will keep the session initialization header.
    -   It will inject your `summary_checkpoint` as a new starting point.
    -   It will preserve the last 3 messages to maintain the immediate flow.

## Tools

### `get_context_stats`
Returns the file size and line count of the current active session history file.

### `prune_history`
Truncates the history file. 
- **Requirement:** You MUST provide a high-quality `summary_checkpoint`.
- **Impact:** Previous verbose history will be physically removed from the file, freeing up tokens for future turns.
