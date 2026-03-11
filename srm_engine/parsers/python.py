"""
python.py — Python import parser using the built-in ast module.

Handles .py files. Extracts both `import X` and `from X import Y` statements.
Resolves relative imports (from . import, from ..pkg import) and project-local
absolute imports against the project root.
"""

import ast
import os

from srm_engine.parsers.base import LanguageParser


class PythonParser(LanguageParser):
    """Extracts and resolves Python import statements using the ast module."""

    extensions = [".py"]

    def extract_imports(self, file_path: str) -> list[str]:
        try:
            with open(file_path, "r", encoding="utf8") as f:
                source = f.read()
        except (OSError, UnicodeDecodeError):
            return []

        try:
            tree = ast.parse(source, filename=file_path)
        except SyntaxError:
            return []

        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    # Prefix with dots for relative imports (e.g. "..utils" -> "..utils")
                    prefix = "." * (node.level or 0)
                    imports.append(prefix + node.module)
                elif node.level:
                    # `from . import something` — just dots
                    imports.append("." * node.level)
        return imports

    def resolve_import(
        self, import_path: str, current_file: str, root_dir: str
    ) -> str | None:
        root_dir = os.path.abspath(root_dir)
        curr_dir = os.path.dirname(current_file)

        if import_path.startswith("."):
            return self._resolve_relative(import_path, curr_dir, root_dir)
        else:
            return self._resolve_absolute(import_path, root_dir)

    def _resolve_relative(
        self, import_path: str, curr_dir: str, root_dir: str
    ) -> str | None:
        # Count leading dots
        level = 0
        while level < len(import_path) and import_path[level] == ".":
            level += 1
        module_part = import_path[level:]

        # Walk up `level` directories (level=1 means current package dir)
        base = curr_dir
        for _ in range(level - 1):
            base = os.path.dirname(base)

        if module_part:
            parts = module_part.split(".")
            candidate = os.path.join(base, *parts)
        else:
            candidate = base

        return self._find_module(candidate, root_dir)

    def _resolve_absolute(self, import_path: str, root_dir: str) -> str | None:
        parts = import_path.split(".")
        candidate = os.path.join(root_dir, *parts)
        return self._find_module(candidate, root_dir)

    def _find_module(self, candidate: str, root_dir: str) -> str | None:
        # candidate.py
        py_file = candidate + ".py"
        if os.path.isfile(py_file) and py_file.startswith(root_dir):
            return py_file

        # candidate/__init__.py (package)
        init_file = os.path.join(candidate, "__init__.py")
        if os.path.isfile(init_file) and init_file.startswith(root_dir):
            return init_file

        return None
