import os
from pathlib import Path
import networkx as nx
from srm_engine.parsers import get_parser_for_file, supported_extensions


def extract_imports(file_path):
    """AST-based import extraction. Auto-detects language from file extension."""
    parser = get_parser_for_file(file_path)
    if parser is None:
        return []
    try:
        return parser.extract_imports(file_path)
    except Exception:
        return []


def resolve_import(import_path, current_file, root_dir):
    """Resolves an import string to an absolute file path within the root_dir."""
    parser = get_parser_for_file(current_file)
    if parser is None:
        return None
    return parser.resolve_import(import_path, current_file, root_dir)


def build_graph(root_dir):
    """Builds a NetworkX DiGraph representing the project dependency structure.

    Auto-detects supported languages by file extension and uses the
    appropriate parser for each file.
    """
    G = nx.DiGraph()
    exts = tuple(supported_extensions())

    files_to_process = []
    for root, _, files in os.walk(root_dir):
        for file in files:
            if file.endswith(exts):
                files_to_process.append(os.path.join(root, file))

    for file in files_to_process:
        G.add_node(os.path.abspath(file))

    for file in files_to_process:
        abs_file = os.path.abspath(file)
        imports = extract_imports(file)
        for imp in imports:
            resolved = resolve_import(imp, abs_file, root_dir)
            if resolved and os.path.exists(resolved):
                G.add_edge(abs_file, resolved)

    return G

if __name__ == "__main__":
    # Test on the generated maze
    target = os.path.join(os.path.dirname(__file__), "../target_repo")
    if os.path.exists(target):
        graph = build_graph(target)
        print(f"Graph built with {graph.number_of_nodes()} nodes and {graph.number_of_edges()} edges.")
        
        # Find the path from HeaderWidget.vue to authStore.ts
        try:
            # We need to find the specific absolute paths
            nodes = list(graph.nodes())
            header = [n for n in nodes if "HeaderWidget.vue" in n][0]
            auth = [n for n in nodes if "authStore.ts" in n][0]
            
            path = nx.shortest_path(graph, source=header, target=auth)
            print("Found dependency path:")
            for p in path:
                print(f"  - {os.path.relpath(p, target)}")
        except Exception as e:
            print(f"Path not found: {e}")
