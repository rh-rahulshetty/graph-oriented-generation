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
from datetime import datetime, timezone

# Suppress model loading noise on stderr
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
warnings.filterwarnings("ignore")


def _log_interaction(data_dir: str, entry: dict):
    """Append an interaction entry to .gog/interactions.jsonl"""
    log_path = os.path.join(data_dir, "interactions.jsonl")
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        pass


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
    session_id = hook_input.get("session_id", None)
    if not prompt.strip():
        return

    if not os.path.exists(graph_path) or not os.path.exists(emb_path):
        print("GOG hook: graph not built. Run `gog build <project>` first.", file=sys.stderr)
        return

    with open(graph_path, "rb") as f:
        graph = pickle.load(f)
    with open(emb_path, "rb") as f:
        node_embeddings = pickle.load(f)

    total_nodes = graph.number_of_nodes()
    relevant_files = isolate_context(graph, prompt, node_embeddings=node_embeddings)

    # Determine outcome
    if not relevant_files:
        _log_interaction(data_dir, {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": session_id,
            "prompt": prompt,
            "result": "no_files",
            "files_isolated": 0,
            "files_total": total_nodes,
            "files": [],
        })
        return

    if len(relevant_files) == total_nodes:
        _log_interaction(data_dir, {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": session_id,
            "prompt": prompt,
            "result": "no_seeds_matched",
            "files_isolated": total_nodes,
            "files_total": total_nodes,
            "files": [],
        })
        return

    # Build context string with file contents
    rel_paths = []
    parts = [f"[GOG Context] Found {len(relevant_files)} relevant files via graph traversal:", ""]

    for fpath in relevant_files:
        rel = os.path.relpath(fpath, project_dir)
        rel_paths.append(rel)
        parts.append(f"--- {rel} ---")
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                parts.append(f.read())
        except (OSError, UnicodeDecodeError):
            parts.append("(could not read file)")
        parts.append("")

    _log_interaction(data_dir, {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "prompt": prompt,
        "result": "context_provided",
        "files_isolated": len(relevant_files),
        "files_total": total_nodes,
        "files": rel_paths,
    })

    output = {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": "\n".join(parts),
        }
    }
    print(json.dumps(output))
