# ContextCleaner-MCP v2.0 — Selective Pruning

Универсальный сервер контекст-менеджмента для любого MCP-совместимого CLI (Kimi, Claude Desktop, Cursor, Windsurf, и др.).

## Когда использовать

1. **Давление контекста** — если сессия разрослась (>70% лимита токенов).
2. **Завершение подзадачи** — после завершения сложного шага очистите промежуточные логи.
3. **Длинные сессии** — каждые 10-15 сообщений проверяйте `get_context_stats`.

## Как это работает

Вместо грубого truncation (обрезания последних N сообщений) сервер использует **selective pruning**:

- Сообщения помечаются флагом `metadata.prune = true`
- Удаляется только помеченный мусор: reasoning, tool outputs, intermediate code
- Сохраняются критические сообщения: system, user, final answers
- Перед удалением создаётся `.backup`

## Workflow

```text
Step 1: Проверка
→ get_context_stats()
   Возвращает: total_messages, total_tokens, marked_for_pruning, potential_savings_percent

Step 2: Маркировка (выполняется автоматически клиентом или вручную)
→ mark_for_pruning(
    types=["reasoning", "tool_output", "intermediate"],
    reason="task completed"
  )

Step 3: Очистка
→ prune_marked()
   Удаляет все сообщения с metadata.prune = true
   Создаёт backup автоматически

Step 4: Проверка результата
→ get_context_stats()
```

## Инструменты

### `get_context_stats`
Возвращает статистику сессии: размер, токены, количество помеченных сообщений, потенциальную экономию.

### `mark_for_pruning`
Помечает сообщения для удаления по критериям:
- `ids` — конкретные ID
- `types` — типы сообщений (reasoning, tool_output, intermediate)
- `roles` — роли (assistant, tool)
- `content_pattern` — подстрока в content

### `prune_marked`
Удаляет все помеченные сообщения. Создаёт бэкап автоматически.

### `restore_backup`
Восстанавливает сессию из последнего бэкапа.

### `list_messages`
Возвращает список сообщений с их статусом prune и оценкой токенов.

## Отличие от v1.0 (truncation)

| | v1.0 ( truncation) | v2.0 (selective pruning) |
|--|---------------------|--------------------------|
| Логика | Оставить последние N | Удалить только помеченные |
| System prompt | Может потеряться | Всегда сохраняется |
| User запросы | Могут потеряться | Всегда сохраняются |
| Финальный код | Может потеряться | Всегда сохраняется |
| Мусор | Может остаться | Удаляется полностью |
| Бэкап | Нет | Автоматический |

## Универсальность

Сервер работает с любым MCP-клиентом:
- **Kimi CLI** — `kimi mcp add --transport stdio ...`
- **Claude Desktop** — `claude_desktop_config.json`
- **Cursor** — `.cursor/mcp.json`
- **Generic** — stdin/stdout JSON-RPC

Конфиги для всех клиентов лежат в корне репозитория.
