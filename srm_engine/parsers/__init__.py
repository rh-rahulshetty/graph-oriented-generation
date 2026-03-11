"""
parsers — Language-specific import parsers with auto-detection.

To add a new language:
    1. Create a new module in this directory (e.g. rust.py)
    2. Subclass LanguageParser and set `extensions`
    3. Import and register it in PARSER_REGISTRY below
"""

import os

from srm_engine.parsers.base import LanguageParser
from srm_engine.parsers.typescript import TypeScriptParser
from srm_engine.parsers.python import PythonParser

# Registry: each parser instance handles one or more file extensions.
# Order doesn't matter — extensions must not overlap between parsers.
PARSER_REGISTRY: list[LanguageParser] = [
    TypeScriptParser(),
    PythonParser(),
]

# Built at import time from the registry
_EXT_TO_PARSER: dict[str, LanguageParser] = {}
for _parser in PARSER_REGISTRY:
    for _ext in _parser.extensions:
        _EXT_TO_PARSER[_ext] = _parser


def get_parser_for_file(file_path: str) -> LanguageParser | None:
    """Return the parser that handles this file's extension, or None."""
    ext = os.path.splitext(file_path)[1].lower()
    return _EXT_TO_PARSER.get(ext)


def supported_extensions() -> set[str]:
    """Return all file extensions that have a registered parser."""
    return set(_EXT_TO_PARSER.keys())


def detect_languages(root_dir: str) -> dict[str, int]:
    """Scan a directory and return a {extension: file_count} map for supported files."""
    counts: dict[str, int] = {}
    exts = supported_extensions()
    for dirpath, _, filenames in os.walk(root_dir):
        for fname in filenames:
            ext = os.path.splitext(fname)[1].lower()
            if ext in exts:
                counts[ext] = counts.get(ext, 0) + 1
    return counts
