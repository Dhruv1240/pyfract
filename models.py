from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple


@dataclass
class SymbolInfo:
    """Tracks a symbol's type, scope, and usage context."""

    name: str
    kind: str
    scope: str
    defined_at_line: int
    is_builtin: bool = False


@dataclass
class Segment:
    identifier: str
    kind: str
    name: str
    start_line: int
    end_line: int
    code: str
    signature: str
    dependencies: List[str]
    defined_symbols: List[str] = field(default_factory=list)
    local_symbols: List[str] = field(default_factory=list)
    external_refs: Dict[str, str] = field(default_factory=dict)
    used_attributes: List[Tuple[str, str]] = field(default_factory=list)
