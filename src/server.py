"""
ContextCleaner-MCP v2.0 — Selective Pruning Server

Удаляет только помеченные сообщения (metadata.prune=true),
сохраняя критически важный контекст.

Безопасность:
- Автоматические бэкапы перед любыми изменениями
- Atomic write (запись во временный файл + rename)
- Валидация JSON при чтении
"""

import sys
import io

# Принудительная UTF-8 для stdin/stdout на Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)
sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding='utf-8')

import json
import os
import glob
import shutil
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone


class SessionManager:
    def __init__(self, session_dir: str):
        self.session_dir = os.path.abspath(session_dir)
        os.makedirs(self.session_dir, exist_ok=True)

    def get_current_session_file(self) -> Optional[str]:
        list_of_files = glob.glob(os.path.join(self.session_dir, "*.jsonl"))
        if not list_of_files:
            return None
        return max(list_of_files, key=os.path.getmtime)

    def read_session(self, filepath: str) -> List[Dict[str, Any]]:
        messages = []
        with open(filepath, "r", encoding="utf-8") as f:
            for i, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    messages.append(json.loads(line))
                except json.JSONDecodeError as e:
                    messages.append({
                        "_raw": line,
                        "_line": i,
                        "_error": str(e),
                        "id": f"corrupt-{i}",
                        "type": "corrupt"
                    })
        return messages

    def write_session(self, filepath: str, messages: List[Dict[str, Any]]) -> None:
        temp_path = filepath + ".tmp"
        with open(temp_path, "w", encoding="utf-8") as f:
            for msg in messages:
                f.write(json.dumps(msg, ensure_ascii=False) + "\n")
        shutil.move(temp_path, filepath)

    def create_backup(self, filepath: str) -> str:
        backup_path = filepath + ".backup"
        shutil.copy2(filepath, backup_path)
        return backup_path

    def restore_backup(self, filepath: str) -> bool:
        backup_path = filepath + ".backup"
        if not os.path.exists(backup_path):
            return False
        shutil.copy2(backup_path, filepath)
        return True

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Смешанная эвристика: в среднем 1 токен ≈ 3-4 символа для кода/текста."""
        return max(1, len(text) // 3)

    def message_to_text(self, msg: Dict[str, Any]) -> str:
        """Извлекает полное текстовое представление сообщения для подсчёта токенов."""
        parts = []
        if "role" in msg:
            parts.append(msg["role"])
        if "type" in msg:
            parts.append(msg["type"])
        content = msg.get("content", "")
        if isinstance(content, str):
            parts.append(content)
        elif isinstance(content, list):
            for item in content:
                if isinstance(item, dict):
                    if "text" in item:
                        parts.append(item["text"])
                    elif "code" in item:
                        parts.append(item["code"])
        if "tool_calls" in msg:
            for tc in msg["tool_calls"]:
                parts.append(json.dumps(tc))
        if "tool_call_id" in msg:
            parts.append(msg.get("name", ""))
            parts.append(str(msg.get("content", "")))
        if "name" in msg:
            parts.append(msg["name"])
        return "\n".join(parts)

    def get_stats(self, filepath: str) -> Dict[str, Any]:
        messages = self.read_session(filepath)
        file_size = os.path.getsize(filepath)

        total_tokens = 0
        marked_tokens = 0
        marked_count = 0
        valid_messages = []

        for msg in messages:
            if "_error" in msg:
                continue
            valid_messages.append(msg)
            text = self.message_to_text(msg)
            tokens = self.estimate_tokens(text)
            total_tokens += tokens

            if msg.get("metadata", {}).get("prune") is True:
                marked_tokens += tokens
                marked_count += 1

        return {
            "file_path": filepath,
            "file_size_bytes": file_size,
            "total_lines": len(messages),
            "total_messages": len(valid_messages),
            "total_tokens": total_tokens,
            "marked_for_pruning": marked_count,
            "marked_tokens": marked_tokens,
            "potential_savings_percent": round(marked_tokens / total_tokens * 100, 2) if total_tokens > 0 else 0.0,
            "corrupt_lines": len(messages) - len(valid_messages)
        }

    def mark_messages(self, filepath: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        messages = self.read_session(filepath)
        marked = 0
        matched_ids = []
        already_marked = 0
        reason = arguments.get("reason", "manual")

        ids_set = set(arguments.get("ids", []))
        types_set = set(arguments.get("types", []))
        roles_set = set(arguments.get("roles", []))
        pattern = arguments.get("content_pattern")

        for msg in messages:
            if "_error" in msg:
                continue

            # Если уже помечено — считаем, но не перезаписываем
            if msg.get("metadata", {}).get("prune") is True:
                already_marked += 1
                continue

            should_mark = False

            if ids_set and msg.get("id") in ids_set:
                should_mark = True
            if types_set and msg.get("type") in types_set:
                should_mark = True
            if roles_set and msg.get("role") in roles_set:
                should_mark = True
            if pattern:
                content = str(msg.get("content", ""))
                if pattern in content:
                    should_mark = True

            if should_mark:
                if "metadata" not in msg:
                    msg["metadata"] = {}
                msg["metadata"]["prune"] = True
                msg["metadata"]["prune_reason"] = reason
                msg["metadata"]["pruned_at"] = datetime.now(timezone.utc).isoformat()
                marked += 1
                matched_ids.append(msg.get("id"))

        if marked > 0:
            self.create_backup(filepath)
            self.write_session(filepath, messages)

        return {
            "status": "marked",
            "newly_marked": marked,
            "already_marked": already_marked,
            "matched_ids": matched_ids
        }

    def prune_marked(self, filepath: str) -> Dict[str, Any]:
        messages = self.read_session(filepath)
        original_count = len([m for m in messages if "_error" not in m])
        original_tokens = sum(
            self.estimate_tokens(self.message_to_text(m))
            for m in messages if "_error" not in m
        )

        pruned_ids = []
        kept_messages = []
        corrupt_kept = []

        for msg in messages:
            if "_error" in msg:
                corrupt_kept.append(msg)
                continue
            if msg.get("metadata", {}).get("prune") is True:
                pruned_ids.append(msg.get("id"))
            else:
                kept_messages.append(msg)

        if not pruned_ids:
            return {
                "status": "no_op",
                "message": "No messages marked for pruning found."
            }

        final_messages = kept_messages + corrupt_kept
        new_tokens = sum(
            self.estimate_tokens(self.message_to_text(m))
            for m in final_messages if "_error" not in m
        )

        self.create_backup(filepath)
        self.write_session(filepath, final_messages)

        return {
            "status": "success",
            "original_count": original_count,
            "pruned_count": len(pruned_ids),
            "kept_count": len(kept_messages),
            "original_tokens": original_tokens,
            "new_tokens": new_tokens,
            "tokens_saved": original_tokens - new_tokens,
            "savings_percent": round((original_tokens - new_tokens) / original_tokens * 100, 2) if original_tokens > 0 else 0.0,
            "pruned_ids": pruned_ids,
            "backup_created": True
        }

    def list_messages(self, filepath: str, show_pruned_only: bool = False) -> List[Dict[str, Any]]:
        messages = self.read_session(filepath)
        output = []
        for msg in messages:
            if "_error" in msg:
                continue
            is_pruned = msg.get("metadata", {}).get("prune") is True
            if show_pruned_only and not is_pruned:
                continue
            content = str(msg.get("content", ""))
            output.append({
                "id": msg.get("id"),
                "type": msg.get("type"),
                "role": msg.get("role"),
                "prune": is_pruned,
                "reason": msg.get("metadata", {}).get("prune_reason") if is_pruned else None,
                "token_estimate": self.estimate_tokens(self.message_to_text(msg)),
                "preview": content[:120] + "..." if len(content) > 120 else content
            })
        return output


def handle_request(request: Dict[str, Any], session_dir: str) -> Dict[str, Any]:
    manager = SessionManager(session_dir)
    method = request.get("method")
    params = request.get("params", {})

    if method == "initialize":
        return {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "context-cleaner-selective", "version": "2.0.0"}
        }

    if method == "tools/list":
        return {
            "tools": [
                {
                    "name": "get_context_stats",
                    "description": "Get statistics about current session including marked messages and potential token savings.",
                    "inputSchema": {"type": "object", "properties": {}}
                },
                {
                    "name": "mark_for_pruning",
                    "description": "Mark specific messages for pruning by IDs, types, roles, or content patterns. Creates backup on change.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "ids": {"type": "array", "items": {"type": "string"}, "description": "Message IDs to mark"},
                            "types": {"type": "array", "items": {"type": "string"}, "description": "Message types to mark (e.g., tool_output, reasoning)"},
                            "roles": {"type": "array", "items": {"type": "string"}, "description": "Message roles to mark"},
                            "content_pattern": {"type": "string", "description": "Substring to search in content"},
                            "reason": {"type": "string", "description": "Reason for pruning"}
                        }
                    }
                },
                {
                    "name": "prune_marked",
                    "description": "Remove all messages with metadata.prune=true. Creates backup automatically.",
                    "inputSchema": {"type": "object", "properties": {}}
                },
                {
                    "name": "restore_backup",
                    "description": "Restore session from the last backup created before pruning/mark.",
                    "inputSchema": {"type": "object", "properties": {}}
                },
                {
                    "name": "list_messages",
                    "description": "List session messages with prune status and token estimates.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "show_pruned_only": {"type": "boolean", "default": False}
                        }
                    }
                }
            ]
        }

    session_file = manager.get_current_session_file()
    if not session_file and method == "tools/call":
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({"error": "No active session file found in " + manager.session_dir}, indent=2)
            }],
            "isError": True
        }

    if method == "tools/call":
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        if tool_name == "get_context_stats":
            stats = manager.get_stats(session_file)
            return {"content": [{"type": "text", "text": json.dumps(stats, indent=2)}]}

        if tool_name == "mark_for_pruning":
            result = manager.mark_messages(session_file, arguments)
            return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}

        if tool_name == "prune_marked":
            result = manager.prune_marked(session_file)
            return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}

        if tool_name == "restore_backup":
            success = manager.restore_backup(session_file)
            return {"content": [{"type": "text", "text": json.dumps({"status": "restored" if success else "error", "message": "Backup not found" if not success else "OK"}, indent=2)}]}

        if tool_name == "list_messages":
            show_pruned_only = arguments.get("show_pruned_only", False)
            msgs = manager.list_messages(session_file, show_pruned_only)
            return {"content": [{"type": "text", "text": json.dumps(msgs, indent=2, ensure_ascii=False)}]}

    return {"error": {"code": -32601, "message": "Method not found"}}


def main():
    session_dir = os.environ.get(
        "SESSION_DIR",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tmp", "chats")
    )
    session_dir = os.path.abspath(session_dir)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            response = handle_request(request, session_dir)
            if "id" in request:
                print(json.dumps({"jsonrpc": "2.0", "id": request["id"], "result": response}))
                sys.stdout.flush()
        except Exception as e:
            error_resp = {
                "jsonrpc": "2.0",
                "id": request.get("id") if isinstance(request, dict) else None,
                "error": {"code": -32603, "message": str(e)}
            }
            print(json.dumps(error_resp))
            sys.stdout.flush()


if __name__ == "__main__":
    main()
