"""
typescript.py — TypeScript/Vue import parser using tree-sitter AST.

Handles .ts and .vue files. Vue files have their <script> block extracted
before parsing. Falls back to regex if tree-sitter fails.
"""

import os
import re

from srm_engine.parsers.base import LanguageParser

try:
    from tree_sitter import Language, Parser
    import tree_sitter_typescript as tstypescript

    try:
        TS_LANGUAGE = Language(tstypescript.language_typescript())
    except AttributeError:
        try:
            TS_LANGUAGE = Language(tstypescript.language())
        except AttributeError:
            TS_LANGUAGE = Language(tstypescript.typescript)  # type: ignore
except Exception:
    TS_LANGUAGE = None

_IMPORT_RE = re.compile(r"import\s+.*?from\s+['\"](.*?)['\"]", re.MULTILINE)
_VUE_SCRIPT_RE = re.compile(r"<script.*?>\s*(.*?)\s*</script>", re.DOTALL)


class TypeScriptParser(LanguageParser):
    """Uses tree-sitter to perform precise AST analysis on TS/Vue files."""

    extensions = [".ts", ".tsx", ".vue"]

    def __init__(self):
        self.parser = Parser(TS_LANGUAGE) if TS_LANGUAGE else None

    def extract_imports(self, file_path: str) -> list[str]:
        if not self.parser or not TS_LANGUAGE:
            return self.extract_imports_with_regex(file_path, _IMPORT_RE)

        try:
            with open(file_path, "rb") as f:
                content = f.read()

            if file_path.endswith(".vue"):
                content = self._extract_vue_script(content)
                if not content:
                    return []

            tree = self.parser.parse(content)
            if not tree:
                return []

            return self._walk_imports(tree.root_node, content)
        except Exception:
            return self.extract_imports_with_regex(file_path, _IMPORT_RE)

    def resolve_import(
        self, import_path: str, current_file: str, root_dir: str
    ) -> str | None:
        curr_dir = os.path.dirname(current_file)

        if import_path.startswith("."):
            potential_path = os.path.normpath(os.path.join(curr_dir, import_path))
        else:
            return None

        for ext in [".ts", ".tsx", ".vue", "/index.ts"]:
            if os.path.exists(potential_path + ext):
                return potential_path + ext
            if potential_path.endswith(ext) and os.path.exists(potential_path):
                return potential_path

        return None

    def _walk_imports(self, node, source: bytes) -> list[str]:
        imports = []
        if node.type == "import_statement":
            for child in node.children:
                if child.type == "string":
                    for sc in child.children:
                        if sc.type == "string_fragment":
                            imports.append(
                                source[sc.start_byte : sc.end_byte].decode(
                                    "utf8", errors="ignore"
                                )
                            )
        for child in node.children:
            imports.extend(self._walk_imports(child, source))
        return imports

    def _extract_vue_script(self, content: bytes) -> bytes | None:
        match = _VUE_SCRIPT_RE.search(content.decode("utf8", errors="ignore"))
        if match:
            return match.group(1).encode("utf8")
        return None
