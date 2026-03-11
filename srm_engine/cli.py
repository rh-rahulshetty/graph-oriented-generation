"""
cli.py — GOG command-line interface.

Commands:
    gog build <project_dir>          Build dependency graph + embeddings for a project
    gog hook install [project_dir]   Install the Claude Code UserPromptSubmit hook
    gog hook test <query>            Test what files GOG isolates for a given query
"""

import argparse
import json
import os
import pickle
import sys

from rich.console import Console

console = Console()

# Default directory for storing graph artifacts
DATA_DIR_NAME = ".gog"


def _get_data_dir(project_dir: str) -> str:
    data_dir = os.path.join(project_dir, DATA_DIR_NAME)
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


def cmd_build(args):
    """Build the dependency graph and pre-compute embeddings for a project."""
    from srm_engine import ast_parser
    from srm_engine.graph_search import build_node_embeddings

    project_dir = os.path.abspath(args.project_dir)
    if not os.path.isdir(project_dir):
        console.print(f"[red]Error:[/] {project_dir} is not a directory")
        sys.exit(1)

    data_dir = _get_data_dir(project_dir)

    from srm_engine.parsers import detect_languages

    console.print(f"Scanning [bold]{project_dir}[/]")

    detected = detect_languages(project_dir)
    if detected:
        lang_parts = [f"{ext} ({count})" for ext, count in sorted(detected.items())]
        console.print(f"Detected: {', '.join(lang_parts)}")
    else:
        console.print("[yellow]No supported files found.[/]")
        sys.exit(1)

    graph = ast_parser.build_graph(project_dir)
    console.print(f"Graph: {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges")

    graph_path = os.path.join(data_dir, "graph.pkl")
    with open(graph_path, "wb") as f:
        pickle.dump(graph, f)

    console.print("Computing node embeddings...")
    embeddings = build_node_embeddings(graph)
    emb_path = os.path.join(data_dir, "embeddings.pkl")
    with open(emb_path, "wb") as f:
        pickle.dump(embeddings, f)

    console.print(f"\n[green]Saved to {data_dir}/[/]")
    console.print(f"  graph.pkl      ({graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges)")
    console.print(f"  embeddings.pkl ({len(embeddings)} vectors)")

    console.print("\n[dim]Nodes:[/]")
    for node in sorted(graph.nodes()):
        console.print(f"  {os.path.relpath(node, project_dir)}")

    console.print("\n[dim]Edges:[/]")
    for src, dst in graph.edges():
        console.print(f"  {os.path.relpath(src, project_dir)} -> {os.path.relpath(dst, project_dir)}")


def cmd_hook_install(args):
    """Install the Claude Code UserPromptSubmit hook for a project."""
    project_dir = os.path.abspath(args.project_dir or os.getcwd())
    data_dir = os.path.join(project_dir, DATA_DIR_NAME)

    graph_path = os.path.join(data_dir, "graph.pkl")
    if not os.path.exists(graph_path):
        console.print(f"[red]Error:[/] No graph found at {data_dir}/")
        console.print("Run [bold]gog build <project_dir>[/] first.")
        sys.exit(1)

    # Find the gog executable (the one running right now)
    gog_bin = _find_gog_bin()

    hook_command = f"{gog_bin} hook run --project-dir {project_dir}"

    claude_dir = os.path.join(project_dir, ".claude")
    os.makedirs(claude_dir, exist_ok=True)
    settings_path = os.path.join(claude_dir, "settings.json")

    # Load existing settings or start fresh
    settings = {}
    if os.path.exists(settings_path):
        with open(settings_path, "r") as f:
            try:
                settings = json.load(f)
            except json.JSONDecodeError:
                pass

    hook_entry = {
        "hooks": [
            {
                "type": "command",
                "command": hook_command,
            }
        ]
    }

    hooks = settings.setdefault("hooks", {})
    existing = hooks.get("UserPromptSubmit", [])

    # Check if we already installed a gog hook
    already_installed = any(
        any("gog hook run" in h.get("command", "") for h in entry.get("hooks", []))
        for entry in existing
    )

    if already_installed:
        console.print("[yellow]GOG hook is already installed.[/]")
        console.print(f"  Settings: {settings_path}")
        return

    existing.append(hook_entry)
    hooks["UserPromptSubmit"] = existing
    settings["hooks"] = hooks

    with open(settings_path, "w") as f:
        json.dump(settings, f, indent=2)
        f.write("\n")

    console.print("[green]Hook installed.[/]")
    console.print(f"  Settings: {settings_path}")
    console.print(f"  Command:  {hook_command}")
    console.print("\nClaude Code will now receive GOG context on every prompt in this project.")


def _find_gog_bin() -> str:
    """Find the absolute path to the gog executable."""
    # If running via `uv run gog`, sys.argv[0] might be the script path
    # Best bet: check if `gog` is on PATH via the current python's scripts dir
    import shutil

    # Check if 'gog' is on PATH
    gog_on_path = shutil.which("gog")
    if gog_on_path:
        return os.path.abspath(gog_on_path)

    # Fallback: use the python that's running us + -m
    return f"{sys.executable} -m srm_engine.cli"


def cmd_hook_run(args):
    """Execute the hook — reads stdin JSON, returns GOG context on stdout."""
    from srm_engine.claude_hook import run_hook
    run_hook(args.project_dir)


def cmd_hook_test(args):
    """Test what files GOG isolates for a query, without running as a hook."""
    from srm_engine.graph_search import isolate_context

    project_dir = os.path.abspath(args.project_dir or os.getcwd())
    data_dir = os.path.join(project_dir, DATA_DIR_NAME)

    graph_path = os.path.join(data_dir, "graph.pkl")
    emb_path = os.path.join(data_dir, "embeddings.pkl")

    if not os.path.exists(graph_path):
        console.print(f"[red]Error:[/] No graph found at {data_dir}/")
        console.print("Run [bold]gog build <project_dir>[/] first.")
        sys.exit(1)

    with open(graph_path, "rb") as f:
        graph = pickle.load(f)
    with open(emb_path, "rb") as f:
        embeddings = pickle.load(f)

    query = " ".join(args.query)
    total = graph.number_of_nodes()

    files = isolate_context(graph, query, node_embeddings=embeddings)

    if len(files) == total:
        console.print(f"\n[yellow]No specific seeds matched for:[/] {query}")
        console.print(f"  Would return all {total} files (no context filtering)")
        return

    console.print(f"\n[bold]Query:[/] {query}")
    console.print(f"[green]{len(files)}/{total}[/] files isolated:\n")
    for fpath in files:
        console.print(f"  {os.path.relpath(fpath, project_dir)}")


def main():
    parser = argparse.ArgumentParser(
        prog="gog",
        description="Graph-Oriented Generation — deterministic context for Claude Code",
    )
    sub = parser.add_subparsers(dest="command")

    # gog build <project_dir>
    p_build = sub.add_parser("build", help="Build dependency graph for a project")
    p_build.add_argument("project_dir", help="Root directory of the project to scan")

    # gog hook ...
    p_hook = sub.add_parser("hook", help="Claude Code hook management")
    hook_sub = p_hook.add_subparsers(dest="hook_command")

    # gog hook install [project_dir]
    p_install = hook_sub.add_parser("install", help="Install the Claude Code hook")
    p_install.add_argument("project_dir", nargs="?", default=None, help="Project directory (default: cwd)")

    # gog hook run --project-dir <dir>
    p_run = hook_sub.add_parser("run", help="Execute the hook (called by Claude Code)")
    p_run.add_argument("--project-dir", required=True, help="Project directory")

    # gog hook test <query...>
    p_test = hook_sub.add_parser("test", help="Test what files GOG isolates for a query")
    p_test.add_argument("--project-dir", default=None, help="Project directory (default: cwd)")
    p_test.add_argument("query", nargs="+", help="Natural language query to test")

    args = parser.parse_args()

    if args.command == "build":
        cmd_build(args)
    elif args.command == "hook":
        if args.hook_command == "install":
            cmd_hook_install(args)
        elif args.hook_command == "run":
            cmd_hook_run(args)
        elif args.hook_command == "test":
            cmd_hook_test(args)
        else:
            p_hook.print_help()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
