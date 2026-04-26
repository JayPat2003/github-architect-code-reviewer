"""
Tool schemas passed to the OpenAI chat API for the agentic review loop.
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "fetch_file_content",
            "description": (
                "Fetch detailed changed-file context from the PR, including patch and "
                "metadata (status, additions, deletions). Use this for deeper inspection."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "Exact file path as it appears in the PR"}
                },
                "required": ["filename"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_architecture_doc",
            "description": (
                "Retrieve the most relevant architecture-document chunks for a topic. "
                "Use this repeatedly with focused queries before flagging violations."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Topic or keyword to search for (e.g. 'secrets', 'retry', 'logging')"},
                    "max_chunks": {"type": "integer", "description": "Maximum relevant chunks to return (default 5)"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "flag_violation",
            "description": "Record a specific architecture violation found in the PR. Call once per distinct issue.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file":       {"type": "string"},
                    "line":       {"type": "integer", "description": "Line number (if known)"},
                    "severity":   {"type": "string", "enum": ["error", "warning", "info"]},
                    "message":    {"type": "string"},
                    "suggestion": {"type": "string"}
                },
                "required": ["file", "severity", "message", "suggestion"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "finish_review",
            "description": (
                "Signal that the review is complete. "
                "Call this ONLY after you have inspected ALL changed files. "
                "passed must be false if any 'error' severity violations were found."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "passed":  {"type": "boolean"},
                    "summary": {"type": "string", "description": "One-paragraph overall assessment"}
                },
                "required": ["passed", "summary"]
            }
        }
    }
]