from __future__ import annotations

import ast
from pathlib import Path
from typing import Dict, List, Set, Tuple

from .models import Segment, SymbolInfo


class SourceAnalyzer:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.builtins = {
            "print",
            "len",
            "str",
            "int",
            "dict",
            "list",
            "set",
            "tuple",
            "open",
            "close",
            "range",
            "enumerate",
            "zip",
            "map",
            "filter",
            "True",
            "False",
            "None",
            "self",
            "cls",
            "object",
            "Exception",
            "property",
            "staticmethod",
            "classmethod",
            "__name__",
            "__main__",
        }
        self.module_symbols: Dict[str, SymbolInfo] = {}

    def analyze(self) -> Tuple[str, List[Segment]]:
        source = self.path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        segments: List[Segment] = []
        lines = source.splitlines()

        self._collect_module_symbols(tree)

        for node in tree.body:
            if not hasattr(node, "lineno") or not hasattr(node, "end_lineno"):
                continue
            start = self._segment_start_line(node)
            end = node.end_lineno
            code = "\n".join(lines[start - 1 : end])
            kind, name = self._classify(node)
            identifier = f"{kind}:{name}:{start}"
            signature = self._signature(node)
            defined_symbols = self._defined_symbols_for_top_level_node(node)
            dependencies, local_symbols, external_refs, used_attributes = self._analyze_dependencies(node)

            segments.append(
                Segment(
                    identifier=identifier,
                    kind=kind,
                    name=name,
                    start_line=start,
                    end_line=end,
                    code=code,
                    signature=signature,
                    dependencies=dependencies,
                    defined_symbols=defined_symbols,
                    local_symbols=local_symbols,
                    external_refs=external_refs,
                    used_attributes=used_attributes,
                )
            )

        summary = f"{self.path.name} | {len(lines)} lines | {len(segments)} top-level segments detected."
        return summary, segments

    def _collect_module_symbols(self, tree: ast.AST) -> None:
        for node in tree.body:
            defined_names = self._defined_symbols_for_top_level_node(node)
            if not defined_names:
                continue

            if isinstance(node, ast.FunctionDef):
                kind = "function"
            elif isinstance(node, ast.AsyncFunctionDef):
                kind = "async_function"
            elif isinstance(node, ast.ClassDef):
                kind = "class"
            else:
                kind = "variable"

            for name in defined_names:
                self.module_symbols[name] = SymbolInfo(
                    name=name,
                    kind=kind,
                    scope="module",
                    defined_at_line=getattr(node, "lineno", 0),
                )

    @staticmethod
    def _segment_start_line(node: ast.AST) -> int:
        start = getattr(node, "lineno", 1)
        decorators = getattr(node, "decorator_list", None)
        if decorators:
            decorator_lines = [
                getattr(decorator, "lineno", start)
                for decorator in decorators
                if hasattr(decorator, "lineno")
            ]
            if decorator_lines:
                start = min(start, min(decorator_lines))
        return start

    @staticmethod
    def _classify(node: ast.AST) -> Tuple[str, str]:
        if isinstance(node, ast.FunctionDef):
            return "function", node.name
        if isinstance(node, ast.AsyncFunctionDef):
            return "async_function", node.name
        if isinstance(node, ast.ClassDef):
            return "class", node.name
        end_lineno = getattr(node, "end_lineno", node.lineno)
        return "block", f"block_{node.lineno}_{end_lineno}"

    @staticmethod
    def _assignment_target_names(target: ast.AST) -> List[str]:
        if isinstance(target, ast.Name):
            return [target.id]
        if isinstance(target, (ast.Tuple, ast.List)):
            out: List[str] = []
            for el in target.elts:
                out.extend(SourceAnalyzer._assignment_target_names(el))
            return out
        if isinstance(target, ast.Starred):
            return SourceAnalyzer._assignment_target_names(target.value)
        return []

    @staticmethod
    def _defined_symbols_for_top_level_node(node: ast.AST) -> List[str]:
        names: List[str] = []

        def from_stmt(stmt: ast.stmt) -> None:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.append(stmt.name)
                return
            if isinstance(stmt, ast.Assign):
                for target in stmt.targets:
                    names.extend(SourceAnalyzer._assignment_target_names(target))
                return
            if isinstance(stmt, ast.AnnAssign):
                if isinstance(stmt.target, ast.Name):
                    names.append(stmt.target.id)
                return
            if isinstance(stmt, ast.AugAssign):
                if isinstance(stmt.target, ast.Name):
                    names.append(stmt.target.id)
                return
            if isinstance(stmt, ast.Import):
                for alias in stmt.names:
                    bound = alias.asname if alias.asname else alias.name.split(".")[0]
                    names.append(bound)
                return
            if isinstance(stmt, ast.ImportFrom):
                for alias in stmt.names:
                    if alias.name == "*":
                        continue
                    bound = alias.asname if alias.asname else alias.name
                    names.append(bound)
                return
            if isinstance(stmt, ast.If):
                for child in stmt.body:
                    from_stmt(child)
                for child in stmt.orelse:
                    from_stmt(child)
                return
            if isinstance(stmt, (ast.For, ast.AsyncFor)):
                names.extend(SourceAnalyzer._assignment_target_names(stmt.target))
                for child in stmt.body:
                    from_stmt(child)
                for child in stmt.orelse:
                    from_stmt(child)
                return
            if isinstance(stmt, ast.While):
                for child in stmt.body:
                    from_stmt(child)
                for child in stmt.orelse:
                    from_stmt(child)
                return
            if isinstance(stmt, (ast.With, ast.AsyncWith)):
                for item in stmt.items:
                    if item.optional_vars:
                        names.extend(SourceAnalyzer._assignment_target_names(item.optional_vars))
                for child in stmt.body:
                    from_stmt(child)
                return
            if isinstance(stmt, ast.Try):
                for child in stmt.body:
                    from_stmt(child)
                for handler in stmt.handlers:
                    if handler.name:
                        names.append(handler.name)
                    for child in handler.body:
                        from_stmt(child)
                for child in stmt.orelse:
                    from_stmt(child)
                for child in stmt.finalbody:
                    from_stmt(child)
                return
            match_cls = getattr(ast, "Match", None)
            if match_cls is not None and isinstance(stmt, match_cls):
                for case in stmt.cases:
                    for child in case.body:
                        from_stmt(child)

        if isinstance(node, ast.stmt):
            from_stmt(node)
        return list(dict.fromkeys(names))

    @staticmethod
    def _signature(node: ast.AST) -> str:
        try:
            return ast.unparse(node)[:500]
        except Exception:
            return node.__class__.__name__

    def _analyze_dependencies(self, node: ast.AST) -> Tuple[List[str], List[str], Dict[str, str], List[Tuple[str, str]]]:
        local_scope = LocalScopeAnalyzer()
        dependency_collector = DependencyCollector(self.module_symbols, local_scope)

        dependency_collector.visit(node)

        real_dependencies = []
        for name in dependency_collector.referenced_names:
            if name in self.builtins:
                continue
            if name in local_scope.all_local_symbols:
                continue
            if name in self.module_symbols:
                real_dependencies.append(name)

        return (
            sorted(real_dependencies),
            local_scope.all_local_symbols,
            {
                name: self.module_symbols.get(name, SymbolInfo(name, "unknown", "module", 0)).kind
                for name in real_dependencies
            },
            dependency_collector.attribute_accesses,
        )


class LocalScopeAnalyzer(ast.NodeVisitor):
    """Identifies all locally-defined symbols (local vars, nested functions, etc.)."""

    def __init__(self) -> None:
        self.all_local_symbols: List[str] = []
        self.scope_stack: List[Set[str]] = [set()]

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        for arg in node.args.args:
            self.all_local_symbols.append(arg.arg)
        for arg in node.args.posonlyargs:
            self.all_local_symbols.append(arg.arg)
        for arg in node.args.kwonlyargs:
            self.all_local_symbols.append(arg.arg)
        if node.args.vararg:
            self.all_local_symbols.append(node.args.vararg.arg)
        if node.args.kwarg:
            self.all_local_symbols.append(node.args.kwarg.arg)
        self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            if isinstance(target, ast.Name):
                self.all_local_symbols.append(target.id)
        self.generic_visit(node)


class DependencyCollector(ast.NodeVisitor):
    """Collects dependencies while tracking scope and filtering attributes."""

    def __init__(self, module_symbols: Dict[str, SymbolInfo], local_scope: LocalScopeAnalyzer) -> None:
        self.module_symbols = module_symbols
        self.local_scope = local_scope
        self.referenced_names: Set[str] = set()
        self.attribute_accesses: List[Tuple[str, str]] = []
        self.in_attribute = False

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name):
            self.referenced_names.add(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name):
                obj_name = node.func.value.id
                self.referenced_names.add(obj_name)
                self.attribute_accesses.append((obj_name, node.func.attr))
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Load):
            self.referenced_names.add(node.id)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if isinstance(node.value, ast.Name):
            self.referenced_names.add(node.value.id)
            self.attribute_accesses.append((node.value.id, node.attr))
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        for base in node.bases:
            if isinstance(base, ast.Name):
                self.referenced_names.add(base.id)
        self.generic_visit(node)

    def visit_arg(self, node: ast.arg) -> None:
        if node.annotation and isinstance(node.annotation, ast.Name):
            self.referenced_names.add(node.annotation.id)
        self.generic_visit(node)
