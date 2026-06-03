# Сообщение для коллег

Привет!

Переписал ContextCleaner-MCP с нуля. Теперь это **selective pruning** вместо глупого truncation.

**Что нового:**
- Удаляет только помеченный мусор (reasoning, tool outputs, intermediate код)
- Сохраняет system prompt, user запросы и финальные ответы
- Автобэкап перед каждой очисткой
- Atomic write — не боимся падений
- Реально протестировано через Kimi CLI

**Результаты теста (шахматы):**
- Без MCP: 9 сообщений, 345 токенов
- С MCP: 4 сообщения, 72 токена
- Экономия: **79%**

**Работает с любым CLI:**
- Kimi CLI (проверено)
- Claude Desktop (конфиг готов)
- Cursor (конфиг готов)
- Любой MCP-совместимый клиент

**Как потестить:**
1. `cd ContextCleaner-MCP`
2. Скопируй конфиг под свой CLI (`kimi-mcp-config.json` / `claude-desktop-config.json` / `cursor-mcp-config.json`)
3. `mkdir sessions`
4. Попроси агента написать что-то сложное в несколько итераций, а потом вызвать `prune_marked`

Файлы в репе:
- `src/server.py` — сам сервер
- `INSTALL.md` — универсальная установка
- `AGENT_PROMPT.md` — промпт для агента
- `test_*.py` — тесты

Попробуйте, отпишите что работает / что сломано.
