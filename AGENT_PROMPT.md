# Промпт для агента (universal)

Добавьте этот блок в system prompt или agent instructions вашего CLI.

```markdown
## Context Management Rules

You have access to the **context-cleaner** MCP server with 5 tools. Use them to keep the session context compact and clean.

### Auto-cleanup rules

1. **After every tool call or reasoning step** — the client will auto-mark it as `prune` if it is no longer needed.
2. **Before long operations** — call `get_context_stats` to check context size.
3. **When marked_tokens > 1000 or potential savings > 40%** — call `prune_marked` to free up space.
4. **Never prune** `system`, `user`, or `final` messages.

### Manual cleanup workflow

If auto-cleanup is not active, follow this pattern:

```text
Step 1: Check stats
→ get_context_stats()

Step 2: Mark junk
→ mark_for_pruning(
    types=["reasoning", "tool_output", "intermediate"],
    reason="cleanup after task completion"
  )

Step 3: Prune
→ prune_marked()

Step 4: Verify
→ get_context_stats()
```

### Safety

- A `.backup` file is created automatically before every prune.
- If something goes wrong, call `restore_backup()`.
```
