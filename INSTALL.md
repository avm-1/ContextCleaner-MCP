# Универсальная установка ContextCleaner-MCP

Сервер работает с любым MCP-совместимым клиентом: Kimi CLI, Claude Desktop, Cursor, Windsurf, и т.д.

## Требования

- Python 3.10+
- MCP-совместимый CLI клиент

## Быстрая установка

```bash
git clone <repo-url> context-cleaner
cd context-cleaner
mkdir sessions
```

## Настройка клиентов

### Kimi CLI

```bash
# Скопируйте конфиг
cp kimi-mcp-config.json ~/.kimi/mcp.json

# Проверьте подключение
kimi mcp list
kimi mcp test context-cleaner
```

### Claude Desktop

```bash
# macOS
cp claude-desktop-config.json ~/Library/Application\ Support/Claude/claude_desktop_config.json

# Windows
cp claude-desktop-config.json %APPDATA%\Claude\claude_desktop_config.json
```

### Cursor

```bash
# Внутри Cursor: Settings → MCP → Add Server
# Или скопируйте конфиг в проект
cp cursor-mcp-config.json .cursor/mcp.json
```

### Generic / Ручной запуск

```bash
export SESSION_DIR="./sessions"
python3 src/server.py
```

Сервер читает JSON-RPC из stdin и пишет в stdout.

## Проверка работы

После настройки в любом клиенте доступны 5 инструментов:

- `get_context_stats` — статистика сессии
- `mark_for_pruning` — пометить мусор
- `prune_marked` — удалить помеченное
- `restore_backup` — восстановить из бэкапа
- `list_messages` — список сообщений
