#!/usr/bin/env python3
from __future__ import annotations

from pyfract_core import (
    DependencyCollector,
    LLMPlanner,
    LocalScopeAnalyzer,
    ModuleWriter,
    Segment,
    SourceAnalyzer,
    SymbolInfo,
    app,
    init_config,
    modularize,
    version,
)

__all__ = [
    "DependencyCollector",
    "LLMPlanner",
    "LocalScopeAnalyzer",
    "ModuleWriter",
    "Segment",
    "SourceAnalyzer",
    "SymbolInfo",
    "app",
    "init_config",
    "modularize",
    "main",
    "version",
]


def main() -> None:
    app()


if __name__ == "__main__":
    main()
