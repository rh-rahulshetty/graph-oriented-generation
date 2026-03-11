"""
base.py — Abstract base for language parsers.

Every language parser implements two methods:
    extract_imports(file_path) -> list[str]   Raw import strings from the file.
    resolve_import(import_path, current_file, root_dir) -> str | None
                                              Resolves a raw import string to
                                              an absolute file path, or None
                                              if unresolvable (external package).
"""

import os
import re
from abc import ABC, abstractmethod


class LanguageParser(ABC):
    """Base class for language-specific import parsers."""

    # Subclasses set this to the file extensions they handle (e.g. ['.py'])
    extensions: list[str] = []

    @abstractmethod
    def extract_imports(self, file_path: str) -> list[str]:
        """Return raw import path strings from the given file."""
        ...

    @abstractmethod
    def resolve_import(
        self, import_path: str, current_file: str, root_dir: str
    ) -> str | None:
        """Resolve a raw import string to an absolute file path, or None."""
        ...

    def extract_imports_with_regex(self, file_path: str, pattern: re.Pattern) -> list[str]:
        """Shared fallback: extract imports via regex when AST parsing fails."""
        with open(file_path, "r", encoding="utf8") as f:
            content = f.read()
        return pattern.findall(content)
