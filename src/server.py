import sys
import json
import os
import glob

def get_current_session_file():
    # Attempt to find the most recent session file in the tmp directory
    base_path = "/home/a_v_makarihin/.gemini/tmp/a-v-makarihin/chats/"
    list_of_files = glob.glob(os.path.join(base_path, '*.jsonl'))
    if not list_of_files:
        return None
    return max(list_of_files, key=os.path.getmtime)

def handle_request(request):
    method = request.get("method")
    params = request.get("params", {})

    if method == "initialize":
        return {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {
                    "listChanged": False
                }
            },
            "serverInfo": {
                "name": "context-manager",
                "version": "1.0.0"
            }
        }

    if method == "tools/list":
        return {
            "tools": [
                {
                    "name": "get_context_stats",
                    "description": "Get statistics about the current session history file.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {}
                    }
                },
                {
                    "name": "prune_history",
                    "description": "Truncate the session history file, keeping only the header and the most recent N messages.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "keep_last_n": {
                                "type": "integer",
                                "description": "Number of recent messages to preserve.",
                                "default": 5
                            },
                            "summary_checkpoint": {
                                "type": "string",
                                "description": "A summary of the pruned context to be inserted as a new starting point."
                            }
                        },
                        "required": ["summary_checkpoint"]
                    }
                }
            ]
        }

    if method == "tools/call":
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        session_file = get_current_session_file()
        if not session_file:
            return {"content": [{"type": "text", "text": "Error: No active session file found."}], "isError": True}

        if tool_name == "get_context_stats":
            size = os.path.getsize(session_file)
            with open(session_file, 'r') as f:
                lines = f.readlines()
            return {
                "content": [{
                    "type": "text", 
                    "text": json.dumps({
                        "file_path": session_file,
                        "file_size_bytes": size,
                        "total_lines": len(lines),
                        "estimated_tokens": size // 4 # Rough estimate
                    }, indent=2)
                }]
            }

        if tool_name == "prune_history":
            keep_last_n = arguments.get("keep_last_n", 5)
            summary = arguments.get("summary_checkpoint")

            with open(session_file, 'r') as f:
                lines = f.readlines()

            if len(lines) <= keep_last_n + 1:
                return {"content": [{"type": "text", "text": "History is already short enough."}]}

            header = lines[0]
            last_messages = lines[-keep_last_n:]
            
            # Construct a new history state
            # We inject the summary as a 'gemini' message or a special metadata line
            checkpoint_entry = json.dumps({
                "id": "checkpoint-" + os.urandom(4).hex(),
                "timestamp": "2026-05-25T00:00:00.000Z",
                "type": "gemini",
                "content": f"--- CONTEXT PRUNED. SUMMARY OF PREVIOUS ACTIONS: ---\n{summary}"
            })

            new_content = [header, checkpoint_entry + "\n"] + last_messages

            with open(session_file, 'w') as f:
                f.writelines(new_content)

            return {
                "content": [{
                    "type": "text", 
                    "text": f"Successfully pruned history. Kept header, injected summary, and preserved last {keep_last_n} messages."
                }]
            }

    return {"error": {"code": -32601, "message": "Method not found"}}

def main():
    for line in sys.stdin:
        try:
            request = json.loads(line)
            response = handle_request(request)
            if "id" in request:
                print(json.dumps({"jsonrpc": "2.0", "id": request["id"], "result": response}))
                sys.stdout.flush()
        except Exception as e:
            pass

if __name__ == "__main__":
    main()
