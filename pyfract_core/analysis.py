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
        line_offsets = self._line_start_offsets(source)
        line_count = source.count("\n") + (1 if source else 0) - (1 if source.endswith("\n") else 0)

        self._collect_module_symbols(tree)

        for node in tree.body:
            if not hasattr(node, "lineno") or not hasattr(node, "end_lineno"):
                continue
            start = self._segment_start_line(node)
            end = node.end_lineno
            code = self._slice_source_by_lines(source, line_offsets, start, end)
            kind, name = self._classify(node)
            identifier = f"{kind}:{name}:{start}"
            signature = self._signature(node, source)
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

        summary = f"{self.path.name} | {line_count} lines | {len(segments)} top-level segments detected."
        return summary, segments

    @staticmethod
    def _line_start_offsets(source: str) -> List[int]:
        offsets = [0]
        for index, char in enumerate(source):
            if char == "\n":
                offsets.append(index + 1)
        offsets.append(len(source))
        return offsets

    @staticmethod
    def _slice_source_by_lines(source: str, line_offsets: List[int], start_line: int, end_line: int) -> str:
        if not source:
            return ""
        start = max(1, start_line)
        end = max(start, end_line)
        max_line_index = max(1, len(line_offsets) - 1)
        if start > max_line_index:
            return ""
        end = min(end, max_line_index)
        start_index = line_offsets[start - 1]
        end_index = line_offsets[end] if end < len(line_offsets) else len(source)
        return source[start_index:end_index].rstrip("\n")

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
    def _signature(node: ast.AST, source: str) -> str:
        get_source_segment = getattr(ast, "get_source_segment", None)
        if callable(get_source_segment):
            try:
                segment = get_source_segment(source, node)
                if segment:
                    return segment.strip()[:500]
            except Exception:
                pass

        unparse = getattr(ast, "unparse", None)
        if callable(unparse):
            try:
                return unparse(node)[:500]
            except Exception:
                pass

        return node.__class__.__name__

    def _analyze_dependencies(self, node: ast.AST) -> Tuple[List[str], List[str], Dict[str, str], List[Tuple[str, str]]]:
        local_scope = LocalScopeAnalyzer()
        local_scope.visit(node)
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
    """Identifies locally-defined names with nested-scope awareness."""

    def __init__(self) -> None:
        self.all_local_symbols: List[str] = []
        self.scope_stack: List[Set[str]] = [set()]
        self.global_stack: List[Set[str]] = [set()]
        self._seen_symbols: Set[str] = set()

    def _declare_local(self, name: str) -> None:
        if not name:
            return
        if name in self.global_stack[-1] and len(self.scope_stack) > 1:
            return
        self.scope_stack[-1].add(name)
        if name not in self._seen_symbols:
            self._seen_symbols.add(name)
            self.all_local_symbols.append(name)

    def _bind_target(self, target: ast.AST) -> None:
        if isinstance(target, ast.Name):
            self._declare_local(target.id)
            return
        if isinstance(target, (ast.Tuple, ast.List)):
            for element in target.elts:
                self._bind_target(element)
            return
        if isinstance(target, ast.Starred):
            self._bind_target(target.value)

    def _bind_arguments(self, args: ast.arguments) -> None:
        for arg in args.posonlyargs:
            self._declare_local(arg.arg)
        for arg in args.args:
            self._declare_local(arg.arg)
        if args.vararg:
            self._declare_local(args.vararg.arg)
        for arg in args.kwonlyargs:
            self._declare_local(arg.arg)
        if args.kwarg:
            self._declare_local(args.kwarg.arg)

    def visit_Global(self, node: ast.Global) -> None:
        self.global_stack[-1].update(node.names)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._declare_local(node.name)
        self.scope_stack.append(set())
        self.global_stack.append(set())
        self._bind_arguments(node.args)
        self.generic_visit(node)
        self.scope_stack.pop()
        self.global_stack.pop()

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._declare_local(node.name)
        self.scope_stack.append(set())
        self.global_stack.append(set())
        self.generic_visit(node)
        self.scope_stack.pop()
        self.global_stack.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            self._bind_target(target)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        self._bind_target(node.target)
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        self._bind_target(node.target)
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        self._bind_target(node.target)
        self.generic_visit(node)

    visit_AsyncFor = visit_For

    def visit_With(self, node: ast.With) -> None:
        for item in node.items:
            if item.optional_vars is not None:
                self._bind_target(item.optional_vars)
        self.generic_visit(node)

    visit_AsyncWith = visit_With

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if isinstance(node.name, str):
            self._declare_local(node.name)
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            bound = alias.asname if alias.asname else alias.name.split(".")[0]
            self._declare_local(bound)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for alias in node.names:
            if alias.name == "*":
                continue
            bound = alias.asname if alias.asname else alias.name
            self._declare_local(bound)
        self.generic_visit(node)


class DependencyCollector(ast.NodeVisitor):
    """Collects dependencies while tracking scope and filtering attributes."""

    def __init__(self, module_symbols: Dict[str, SymbolInfo], local_scope: LocalScopeAnalyzer) -> None:
        self.module_symbols = module_symbols
        self.local_scope = local_scope
        self.referenced_names: Set[str] = set()
        self.attribute_accesses: List[Tuple[str, str]] = []
        self.scope_stack: List[Set[str]] = [set()]
        self.global_stack: List[Set[str]] = [set()]

    def _is_local_name(self, name: str) -> bool:
        return any(name in scope for scope in self.scope_stack)

    def _declare_name(self, name: str) -> None:
        if not name:
            return
        if name in self.global_stack[-1] and len(self.scope_stack) > 1:
            return
        self.scope_stack[-1].add(name)

    def _bind_target(self, target: ast.AST) -> None:
        if isinstance(target, ast.Name):
            self._declare_name(target.id)
            return
        if isinstance(target, (ast.Tuple, ast.List)):
            for element in target.elts:
                self._bind_target(element)
            return
        if isinstance(target, ast.Starred):
            self._bind_target(target.value)
            return
        if isinstance(target, ast.Attribute):
            self.visit(target.value)
            return
        if isinstance(target, ast.Subscript):
            self.visit(target.value)
            self.visit(target.slice)

    def _bind_arguments(self, args: ast.arguments) -> None:
        for arg in args.posonlyargs:
            self._declare_name(arg.arg)
        for arg in args.args:
            self._declare_name(arg.arg)
        if args.vararg:
            self._declare_name(args.vararg.arg)
        for arg in args.kwonlyargs:
            self._declare_name(arg.arg)
        if args.kwarg:
            self._declare_name(args.kwarg.arg)

    def _visit_function_common(self, node: ast.AST, args: ast.arguments, body: List[ast.stmt], name: str) -> None:
        self._declare_name(name)
        for decorator in getattr(node, "decorator_list", []):
            self.visit(decorator)
        for default in list(args.defaults) + [value for value in args.kw_defaults if value is not None]:
            self.visit(default)
        for arg in list(args.posonlyargs) + list(args.args) + list(args.kwonlyargs):
            if arg.annotation is not None:
                self.visit(arg.annotation)
        if args.vararg and args.vararg.annotation is not None:
            self.visit(args.vararg.annotation)
        if args.kwarg and args.kwarg.annotation is not None:
            self.visit(args.kwarg.annotation)
        returns = getattr(node, "returns", None)
        if returns is not None:
            self.visit(returns)

        self.scope_stack.append(set())
        self.global_stack.append(set())
        self._bind_arguments(args)
        for stmt in body:
            self.visit(stmt)
        self.scope_stack.pop()
        self.global_stack.pop()

    def _visit_comprehension_scope(
        self,
        generators: List[ast.comprehension],
        tail_nodes: List[ast.AST],
    ) -> None:
        self.scope_stack.append(set())
        self.global_stack.append(set())
        for generator in generators:
            self.visit(generator.iter)
            self._bind_target(generator.target)
            for condition in generator.ifs:
                self.visit(condition)
        for tail_node in tail_nodes:
            self.visit(tail_node)
        self.scope_stack.pop()
        self.global_stack.pop()

    def visit_Global(self, node: ast.Global) -> None:
        self.global_stack[-1].update(node.names)

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name):
            if not self._is_local_name(node.func.id):
                self.referenced_names.add(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name):
                obj_name = node.func.value.id
                if not self._is_local_name(obj_name):
                    self.referenced_names.add(obj_name)
                self.attribute_accesses.append((obj_name, node.func.attr))
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Load):
            if not self._is_local_name(node.id):
                self.referenced_names.add(node.id)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if isinstance(node.value, ast.Name):
            if not self._is_local_name(node.value.id):
                self.referenced_names.add(node.value.id)
            self.attribute_accesses.append((node.value.id, node.attr))
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        self.visit(node.value)
        for target in node.targets:
            self._bind_target(target)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if node.annotation is not None:
            self.visit(node.annotation)
        if node.value is not None:
            self.visit(node.value)
        self._bind_target(node.target)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        self._bind_target(node.target)
        if not isinstance(node.target, ast.Name):
            self.visit(node.target)
        self.visit(node.value)

    def visit_For(self, node: ast.For) -> None:
        self.visit(node.iter)
        self._bind_target(node.target)
        for stmt in node.body:
            self.visit(stmt)
        for stmt in node.orelse:
            self.visit(stmt)

    visit_AsyncFor = visit_For

    def visit_With(self, node: ast.With) -> None:
        for item in node.items:
            self.visit(item.context_expr)
            if item.optional_vars is not None:
                self._bind_target(item.optional_vars)
        for stmt in node.body:
            self.visit(stmt)

    visit_AsyncWith = visit_With

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.type is not None:
            self.visit(node.type)
        if isinstance(node.name, str):
            self._declare_name(node.name)
        for stmt in node.body:
            self.visit(stmt)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            bound = alias.asname if alias.asname else alias.name.split(".")[0]
            self._declare_name(bound)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for alias in node.names:
            if alias.name == "*":
                continue
            bound = alias.asname if alias.asname else alias.name
            self._declare_name(bound)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function_common(node, node.args, node.body, node.name)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Lambda(self, node: ast.Lambda) -> None:
        self.scope_stack.append(set())
        self.global_stack.append(set())
        self._bind_arguments(node.args)
        self.visit(node.body)
        self.scope_stack.pop()
        self.global_stack.pop()

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._declare_name(node.name)
        for decorator in node.decorator_list:
            self.visit(decorator)
        for base in node.bases:
            self.visit(base)
        for keyword in node.keywords:
            self.visit(keyword.value)

        self.scope_stack.append(set())
        self.global_stack.append(set())
        for stmt in node.body:
            self.visit(stmt)
        self.scope_stack.pop()
        self.global_stack.pop()

    def visit_ListComp(self, node: ast.ListComp) -> None:
        self._visit_comprehension_scope(node.generators, [node.elt])

    def visit_SetComp(self, node: ast.SetComp) -> None:
        self._visit_comprehension_scope(node.generators, [node.elt])

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
        self._visit_comprehension_scope(node.generators, [node.elt])

    def visit_DictComp(self, node: ast.DictComp) -> None:
        self._visit_comprehension_scope(node.generators, [node.key, node.value])

    def visit_arg(self, node: ast.arg) -> None:
        if node.annotation and isinstance(node.annotation, ast.Name):
            if not self._is_local_name(node.annotation.id):
                self.referenced_names.add(node.annotation.id)
        self.generic_visit(node)
