"""
claude_hook.py — Claude Code UserPromptSubmit hook.

Called by Claude Code via the command configured in .claude/settings.json.
Receives the user's prompt as JSON on stdin, uses GOG to isolate relevant
files via semantic seeding + graph traversal, and returns their contents
as additionalContext on stdout.
"""

import json
import os
import pickle
import sys
import warnings

# Suppress model loading noise on stderr
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
warnings.filterwarnings("ignore")


def run_hook(project_dir: str):
    from srm_engine.graph_search import isolate_context

    data_dir = os.path.join(project_dir, ".gog")
    graph_path = os.path.join(data_dir, "graph.pkl")
    emb_path = os.path.join(data_dir, "embeddings.pkl")

    # Read hook input from stdin
    raw = sys.stdin.read()
    try:
        hook_input = json.loads(raw)
    except json.JSONDecodeError:
        return

    prompt = hook_input.get("prompt", "")
    if not prompt.strip():
        return

    if not os.path.exists(graph_path) or not os.path.exists(emb_path):
        print("GOG hook: graph not built. Run `gog build <project>` first.", file=sys.stderr)
        return

    with open(graph_path, "rb") as f:
        graph = pickle.load(f)
    with open(emb_path, "rb") as f:
        node_embeddings = pickle.load(f)

    relevant_files = isolate_context(graph, prompt, node_embeddings=node_embeddings)

    if not relevant_files:
        return

    # If all files returned (no seeds matched), skip to avoid noise
    if len(relevant_files) == graph.number_of_nodes():
        return

    # Build context string with file contents
    parts = [f"[GOG Context] Found {len(relevant_files)} relevant files via graph traversal:", ""]

    for fpath in relevant_files:
        rel = os.path.relpath(fpath, project_dir)
        parts.append(f"--- {rel} ---")
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                parts.append(f.read())
        except (OSError, UnicodeDecodeError):
            parts.append("(could not read file)")
        parts.append("")

    output = {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": "\n".join(parts),
        }
    }
    print(json.dumps(output))
