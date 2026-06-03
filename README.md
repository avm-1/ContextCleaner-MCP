# ContextCleaner-MCP v2.0 — Selective Pruning

**English** | [Русский](#русский)

---

<a name="english"></a>

## English

**ContextCleaner-MCP** is a context-management server for the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) that implements **selective pruning** of session messages.

Unlike naive truncation ("keep the last N messages"), this server lets an agent **mark specific messages as irrelevant** and delete only those, preserving critically important context.

### The Problem

In long sessions, agents generate a lot of intermediate data:
- Large tool outputs: JSON, CSV, HTML, logs
- Intermediate reasoning steps that have become obsolete
- Duplicate requests

Simple "keep last N" truncation risks losing:
- Initial system instructions
- Important user clarifications from the middle of the conversation
- Key agent decisions

### Solution: Selective Pruning

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

### Tools

#### `get_context_stats()`
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

#### `mark_for_pruning(criteria)`
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

#### `prune_marked()`
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

#### `restore_backup()`
Restores the session from the latest backup.

#### `list_messages(show_pruned_only)`
Returns a list of messages with their prune status and estimated token count.

### Quick Start

```bash
# Set the directory with .jsonl sessions
export SESSION_DIR="./tmp/chats"

# Start the server
python src/server.py
```

The server reads requests from stdin and writes responses to stdout in JSON-RPC 2.0 format.

### Usage Example

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

### Comparison with Truncation: Real Case (HTML Chess)

A session of developing interactive HTML chess contained 18 messages with heavy tool outputs (docs, logs, base64 screenshots), reasoning steps, and two versions of the final code.

#### What truncation keeps (v1.0, keep_last_n=5)

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

#### What selective pruning keeps

| Kept | Lost |
|------|------|
| system prompt | Kept |
| user-001, user-002, user-003, user-004 | All requirements kept |
| assistant-002 (full code v1) | Kept |
| assistant-003 (patch v2) | Kept |

**Junk fully removed:** 11 messages (reasoning, tool outputs, intermediate code)

#### Final Comparison

| Metric | Selective | Truncation |
|--------|-----------|------------|
| Messages remaining | 7 | 7 |
| Token savings | **79%** (2512 tokens) | 58% (1848 tokens) |
| Critical messages preserved | **7/7** | 4/7 |
| Junk remaining | **0** | 2 (reasoning + base64) |
| Agent can continue work | **Yes** | No |

### Safety

- **Backups:** `.backup` created before any modification
- **Atomic write:** Write to temp file + `shutil.move`
- **JSON validation:** Corrupted lines don't crash the session
- **Idempotency:** Repeated `prune_marked` is safe (no marked messages = no-op)

### Architecture

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

### Testing

```bash
# Basic selective pruning tests
python test_selective_prune.py

# Comparison test: selective vs truncation (chess)
python test_chess_comparison.py

# Comparison with normal LLM workflow (tetris)
python test_tetris_comparison.py

# Real agent with auto-cleanup (without Kimi CLI)
python agent_client.py
```

Tests verify:
1. Marking by type and ID
2. Token counting and savings
3. Deleting only marked messages
4. Preserving critical messages
5. Backup and restore correctness
6. **Context quality comparison** selective pruning vs truncation

### Example 2: Tetris Development (Comparison with Normal LLM Workflow)

A session of developing a full Tetris: 26 messages, 5 iterations, Canvas API, Web Audio, animations.

#### RAW (normal work without cleanup)
- **26 messages, 4240 tokens**
- Quality: 100% (everything in place)
- Problem: 71% of tokens are junk (reasoning, tool outputs, intermediate code)
- In a long session context overflows, each request gets more expensive

#### Selective Pruning
- **10 messages, 1228 tokens**
- Savings: **71% of tokens (3012)**
- Quality: **100%** — all requirements and all code versions preserved
- Junk: **0**

#### Truncation (keep_last_n=5)
- **7 messages, 914 tokens**
- Quality: **40%** — original requirements and final code v1 lost
- Junk: **2** (reasoning + Web Audio test)
- Agent cannot add a new piece or touch controls

#### Modification Capability

| Task | RAW | Selective | Truncation |
|------|-----|-----------|------------|
| Add piece | Yes | Yes | No |
| Change colors | Yes | Yes | No |
| Touch controls | Yes | Yes | No |
| Remove music | Yes | Yes | Yes |
| Change speed | Yes | Yes | No |

#### Economic Benefit

For 100 requests in a long session: **301,200 tokens saved** (~$0.90)
When scaling to thousands of requests, savings become substantial.

### Example 3: Chess Development via Kimi CLI (Real Tests)

Direct comparison of two approaches using real Kimi Code CLI.

#### Without MCP (normal work)

```bash
cd test-chess-without-mcp
kimi --print --prompt "Create a chess board in HTML..."
kimi --print --prompt "Update chess.html to add interactivity..."
```

**Result:**
- `chess.html`: **8202 bytes** (full interactive chess)
- Session: **9 messages, 345 tokens**
- All junk preserved: reasoning, tool outputs, intermediate code

#### With MCP (auto-cleanup)

```bash
cd test-chess-with-mcp
kimi --print --prompt "Create a chess board... After finishing, use context-cleaner MCP to clean up intermediate steps."
```

**Result:**
- `chess.html`: **6049 bytes** (basic + interactive version)
- Session after prune: **4 messages, 72 tokens**
- **Savings: 79% of tokens (273 of 345)**

#### Context Comparison

| Parameter | WITHOUT MCP | WITH MCP |
|-----------|-------------|----------|
| Messages in context | 9 | 4 |
| Tokens | 345 | **72** |
| Junk (reasoning/tool) | 5 | **0** |
| Old code versions | Preserved | **Removed** |
| Backup | No | Yes |

#### What Remains After MCP Cleanup

| ID | Type | Status |
|----|------|--------|
| user-001 | user | Preserved |
| user-002 | user | Preserved |
| assistant-002 | final | Preserved |

#### What Was Removed

| ID | Type | Reason |
|----|------|--------|
| think-001 | reasoning | Intermediate thought |
| tool-001 | tool_output | Validator output |
| assistant-001 | intermediate | Outdated code v1 |
| think-002 | reasoning | Intermediate thought |
| tool-002 | tool_output | Linter output |

#### How It Works in Kimi CLI

1. MCP server is configured in `~/.kimi/mcp.json`
2. When `kimi` starts, it automatically connects to `context-cleaner`
3. Kimi sees 5 tools and can call them by name
4. After code generation, Kimi calls `mark_for_pruning` + `prune_marked`
5. Context is cleaned automatically

#### Connection Confirmation

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

### Requirements

- Python 3.10+
- No external dependencies (stdlib only)

### License

MIT

---

<a name="русский"></a>

[English](#english) | **Русский**

## Русский

**ContextCleaner-MCP** — сервер контекст-менеджмента по протоколу MCP (Model Context Protocol), реализующий **селективное удаление** (selective pruning) сообщений из сессии.

В отличие от наивного truncation ("оставить последние N сообщений"), этот сервер позволяет агенту **помечать конкретные сообщения как неактуальные** и удалять только их, сохраняя критически важный контекст.

### Проблема

В длинных сессиях агент генерирует массу промежуточных данных:
- Большие выводы инструментов (tool outputs): JSON, CSV, HTML, логи
- Промежуточные рассуждения (reasoning), ставшие неактуальными
- Дублирующиеся запросы

Простое обрезание "последних N сообщений" рискует потерять:
- Начальные системные инструкции
- Важные уточнения пользователя из середины диалога
- Ключевые решения агента

### Решение: Selective Pruning

Агент (или клиент) помечает сообщения специальным флагом в `metadata`:

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

MCP сервер находит все помеченные сообщения и безопасно удаляет их:
- Создаёт бэкап перед изменением
- Использует atomic write (запись во временный файл + rename)
- Возвращает статистику экономии токенов

### Инструменты

#### `get_context_stats()`
Возвращает статистику сессии, включая количество помеченных сообщений и потенциальную экономию токенов.

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

#### `mark_for_pruning(criteria)`
Помечает сообщения для удаления по критериям:
- `ids`: массив ID сообщений
- `types`: массив типов (`tool_output`, `reasoning`, ...)
- `roles`: массив ролей (`tool`, `assistant`, ...)
- `content_pattern`: подстрока для поиска в content
- `reason`: причина маркировки (сохраняется в metadata)

```json
{
  "ids": ["tool-001", "tool-002"],
  "types": ["tool_output", "reasoning"],
  "reason": "heavy intermediate data"
}
```

#### `prune_marked()`
Удаляет все сообщения с `metadata.prune = true`.
Автоматически создаёт бэкап `.backup`.

Возвращает детальную статистику:
```json
{
  "status": "success",
  "pruned_count": 8,
  "tokens_saved": 969,
  "savings_percent": 59.7,
  "backup_created": true
}
```

#### `restore_backup()`
Восстанавливает сессию из последнего бэкапа.

#### `list_messages(show_pruned_only)`
Возвращает список сообщений с их статусом prune и оценкой токенов.

### Быстрый старт

```bash
# Указать директорию с .jsonl сессиями
export SESSION_DIR="./tmp/chats"

# Запустить сервер
python src/server.py
```

Сервер читает запросы из stdin и пишет ответы в stdout в формате JSON-RPC 2.0.

### Пример сценария использования

**Сессия: анализ CSV + визуализация**

| ID | Тип | Содержание | Решение |
|----|-----|-----------|---------|
| `sys-001` | system | Инструкции | Оставить |
| `user-001` | user | Запрос | Оставить |
| `think-001` | reasoning | Промежуточная мысль | Пометить |
| `tool-001` | tool_output | `head` CSV (50000 строк) | Пометить |
| `think-002` | reasoning | Промежуточная мысль | Пометить |
| `tool-002` | tool_output | `describe()` вывод | Пометить |
| `assistant-001` | final | Финальный скрипт + объяснение | Оставить |
| `user-002` | user | Уточнение | Оставить |
| `think-004` | reasoning | Промежуточная мысль | Пометить |
| `tool-004` | tool_output | Корреляционная матрица | Пометить |
| `assistant-002` | final | Итоговый ответ | Оставить |

**Результат:**
- До prune: 14 сообщений, 1623 токена
- После prune: 6 сообщений, 654 токена
- **Экономия: 969 токенов (59.7%)**
- Все критические сообщения сохранены

### Сравнение с truncation: реальный кейс (HTML-шахматы)

Сессия разработки интерактивных шахмат в HTML содержала 18 сообщений с тяжёлыми tool outputs (документация, логи, base64-скриншоты), reasoning steps и двумя версиями финального кода.

#### Что оставляет truncation (v1.0, keep_last_n=5)

| Оставлено | Удалено | Проблема |
|-----------|---------|----------|
| system prompt | Сохранено | — |
| checkpoint summary | Сохранено | Генеричная фраза без деталей |
| user-003 (добавь подсветку) | Потеряно | Агент не знает исходного запроса |
| **think-005** (reasoning) | Потеряно | **Мусор сохранён** |
| **tool-005** (base64 image) | Потеряно | **Мусор сохранён** |
| assistant-003 (patch) | Потеряно | Полный код v1 потерян |
| user-004 (perfect!) | Потеряно | — |

**Результат:** агент видит только patch "добавь подсветку", но:
- Не знает, что вообще создавал (нет `user-001`)
- Не имеет полного кода (потерян `assistant-002`)
- Тратит токены на бессмысленный reasoning и base64-изображение

#### Что оставляет selective pruning

| Оставлено | Удалено |
|-----------|---------|
| system prompt | Сохранено |
| user-001, user-002, user-003, user-004 | Все требования сохранены |
| assistant-002 (полный код v1) | Сохранено |
| assistant-003 (patch v2) | Сохранено |

**Мусор удалён полностью:** 11 сообщений (reasoning, tool outputs, intermediate code)

#### Итоговое сравнение

| Метрика | Selective | Truncation |
|---------|-----------|------------|
| Сообщений осталось | 7 | 7 |
| Экономия токенов | **79%** (2512 токенов) | 58% (1848 токенов) |
| Критические сообщения сохранены | **7/7** | 4/7 |
| Мусор остался | **0** | 2 (reasoning + base64) |
| Агент может продолжить работу | **Да** | Нет |

### Безопасность

- **Бэкапы:** Перед любой модификацией создаётся `.backup`
- **Atomic write:** Запись во временный файл + `shutil.move`
- **Валидация JSON:** Повреждённые строки не ломают сессию
- **Идемпотентность:** Повторный `prune_marked` безопасен (нет помеченных → no-op)

### Архитектура

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
                                       | *.jsonl файл |
                                       |  сессии      |
                                       +--------------+
```

### Тестирование

```bash
# Базовые тесты selective pruning
python test_selective_prune.py

# Сравнительный тест: selective vs truncation (шахматы)
python test_chess_comparison.py

# Сравнение с обычной работой LLM (тетрис)
python test_tetris_comparison.py

# Реальный агент с автоочисткой (без Kimi CLI)
python agent_client.py
```

Тесты проверяют:
1. Маркировку по типам и ID
2. Подсчёт токенов и экономии
3. Удаление только помеченных сообщений
4. Сохранение критических сообщений
5. Корректность бэкапа и восстановления
6. **Сравнение качества контекста** selective pruning vs truncation

### Пример 2: разработка Тетриса (сравнение с обычной работой LLM)

Сессия разработки полноценного Тетриса: 26 сообщений, 5 итераций, Canvas API, Web Audio, анимации.

#### RAW (обычная работа без очистки)
- **26 сообщений, 4240 токенов**
- Качество: 100% (всё на месте)
- Проблема: 71% токенов — мусор (reasoning, tool outputs, intermediate code)
- При длинной сессии контекст переполняется, каждый запрос дороже

#### Selective Pruning
- **10 сообщений, 1228 токенов**
- Экономия: **71% токенов (3012)**
- Качество: **100%** — все требования и все версии кода сохранены
- Мусора: **0**

#### Truncation (keep_last_n=5)
- **7 сообщений, 914 токенов**
- Качество: **40%** — потеряны исходные требования и финальный код v1
- Мусора: **2** (reasoning + Web Audio тест)
- Агент не может добавить новую фигуру или touch-управление

#### Способность к модификации

| Задача | RAW | Selective | Truncation |
|--------|-----|-----------|------------|
| Добавить фигуру | Да | Да | Нет |
| Изменить цвета | Да | Да | Нет |
| Touch-управление | Да | Да | Нет |
| Убрать музыку | Да | Да | Да |
| Изменить скорость | Да | Да | Нет |

#### Экономическая выгода

При 100 запросов в длинной сессии: **301,200 токенов сэкономлено** (~$0.90)
При масштабировании на тысячи запросов: экономия становится существенной.

### Пример 3: разработка шахмат через Kimi CLI (реальные тесты)

Проведено прямое сравнение двух подходов с использованием настоящего Kimi Code CLI.

#### Без MCP (обычная работа)

```bash
cd test-chess-without-mcp
kimi --print --prompt "Create a chess board in HTML..."
kimi --print --prompt "Update chess.html to add interactivity..."
```

**Результат:**
- `chess.html`: **8202 байт** (полноценные интерактивные шахматы)
- Сессия: **9 сообщений, 345 токенов**
- Весь мусор сохранён: reasoning, tool outputs, intermediate code

#### С MCP (автоочистка)

```bash
cd test-chess-with-mcp
kimi --print --prompt "Create a chess board... After finishing, use context-cleaner MCP to clean up intermediate steps."
```

**Результат:**
- `chess.html`: **6049 байт** (базовая + интерактивная версия)
- Сессия после prune: **4 сообщения, 72 токена**
- **Экономия: 79% токенов (273 из 345)**

#### Сравнение контекста

| Параметр | БЕЗ MCP | С MCP |
|----------|---------|-------|
| Сообщений в контексте | 9 | 4 |
| Токенов | 345 | **72** |
| Мусора (reasoning/tool) | 5 | **0** |
| Старые версии кода | Сохранены | **Удалены** |
| Бэкап | Нет | **Да** |

#### Что осталось после очистки MCP

| ID | Тип | Статус |
|----|-----|--------|
| user-001 | user | Сохранён |
| user-002 | user | Сохранён |
| assistant-002 | final | Сохранён |

#### Что было удалено

| ID | Тип | Причина |
|----|-----|---------|
| think-001 | reasoning | Промежуточная мысль |
| tool-001 | tool_output | Вывод валидатора |
| assistant-001 | intermediate | Устаревшая версия кода v1 |
| think-002 | reasoning | Промежуточная мысль |
| tool-002 | tool_output | Вывод линтера |

#### Как это работает в Kimi CLI

1. MCP сервер настроен в `~/.kimi/mcp.json`
2. При запуске `kimi` автоматически подключается к `context-cleaner`
3. Kimi видит 5 инструментов и может вызывать их по имени
4. После генерации кода Kimi вызывает `mark_for_pruning` + `prune_marked`
5. Контекст очищается автоматически

#### Подтверждение подключения

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

### Требования

- Python 3.10+
- Нет внешних зависимостей (только stdlib)

### Лицензия

MIT
