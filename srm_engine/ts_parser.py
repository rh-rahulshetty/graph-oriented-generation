"""
ts_parser.py — Backwards-compatible re-export.

The TypeScriptParser implementation has moved to srm_engine/parsers/typescript.py.
This module re-exports it so existing imports continue to work.
"""

from srm_engine.parsers.typescript import TypeScriptParser

__all__ = ["TypeScriptParser"]
