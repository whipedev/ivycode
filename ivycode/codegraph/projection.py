from __future__ import annotations

import ast
from collections.abc import Iterable
from typing import Literal

from pydantic import Field

from ivycode.core.envelope import IvyBaseModel, SymbolBrief

HttpMethod = Literal["GET", "POST", "PUT", "PATCH", "DELETE", "WS"]
DocstringNode = ast.AsyncFunctionDef | ast.FunctionDef | ast.ClassDef | ast.Module

_ROUTE_METHODS: dict[str, HttpMethod] = {
    "get": "GET",
    "post": "POST",
    "put": "PUT",
    "patch": "PATCH",
    "delete": "DELETE",
    "websocket": "WS",
}


class CallEdge(IvyBaseModel):
    caller: str
    callee_name: str


class ParsedRoute(IvyBaseModel):
    method: HttpMethod
    path: str
    handler: str
    framework: Literal["fastapi"] = "fastapi"
    file_path: str


class ParsedModule(IvyBaseModel):
    file_path: str
    module_name: str
    symbols: list[SymbolBrief] = Field(default_factory=list)
    calls: list[CallEdge] = Field(default_factory=list)
    routes: list[ParsedRoute] = Field(default_factory=list)


def parse_python_source(
    *,
    source: str,
    file_path: str,
    module_name: str,
) -> ParsedModule:
    tree = ast.parse(source, filename=file_path)
    symbols: list[SymbolBrief] = []
    calls: list[CallEdge] = []
    routes: list[ParsedRoute] = []

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            class_name = f"{module_name}.{node.name}"
            symbols.append(_class_symbol(node, class_name, file_path))
            for item in node.body:
                if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef):
                    qualified_name = f"{class_name}.{item.name}"
                    symbols.append(
                        _function_symbol(item, qualified_name, file_path, "method")
                    )
                    calls.extend(_calls_for_function(item, qualified_name))
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            qualified_name = f"{module_name}.{node.name}"
            symbols.append(
                _function_symbol(node, qualified_name, file_path, "function")
            )
            calls.extend(_calls_for_function(node, qualified_name))
            routes.extend(_routes_for_function(node, qualified_name, file_path))

    return ParsedModule(
        file_path=file_path,
        module_name=module_name,
        symbols=symbols,
        calls=_dedupe_calls(calls),
        routes=routes,
    )


def _class_symbol(
    node: ast.ClassDef,
    qualified_name: str,
    file_path: str,
) -> SymbolBrief:
    return SymbolBrief(
        qualified_name=qualified_name,
        kind="class",
        file_path=file_path,
        line_start=node.lineno,
        line_end=node.end_lineno or node.lineno,
        signature=f"class {node.name}",
        docstring_summary=_docstring_summary(node),
        callers_count=0,
        callees_count=0,
    )


def _function_symbol(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    qualified_name: str,
    file_path: str,
    kind: Literal["function", "method"],
) -> SymbolBrief:
    return SymbolBrief(
        qualified_name=qualified_name,
        kind=kind,
        file_path=file_path,
        line_start=node.lineno,
        line_end=node.end_lineno or node.lineno,
        signature=_function_signature(node),
        docstring_summary=_docstring_summary(node),
        callers_count=0,
        callees_count=0,
    )


def _function_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    signature = f"{prefix} {node.name}({ast.unparse(node.args)})"
    if node.returns is not None:
        signature = f"{signature} -> {ast.unparse(node.returns)}"
    return signature


def _docstring_summary(node: DocstringNode) -> str | None:
    docstring = ast.get_docstring(node, clean=True)
    if docstring is None:
        return None
    for line in docstring.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return None


def _routes_for_function(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    qualified_name: str,
    file_path: str,
) -> list[ParsedRoute]:
    routes: list[ParsedRoute] = []
    for decorator in node.decorator_list:
        route = _route_from_decorator(decorator, qualified_name, file_path)
        if route is not None:
            routes.append(route)
    return routes


def _route_from_decorator(
    decorator: ast.expr,
    handler: str,
    file_path: str,
) -> ParsedRoute | None:
    if not isinstance(decorator, ast.Call):
        return None
    if not isinstance(decorator.func, ast.Attribute):
        return None
    method = _ROUTE_METHODS.get(decorator.func.attr.lower())
    if method is None:
        return None
    if not decorator.args:
        return None
    path_node = decorator.args[0]
    if not isinstance(path_node, ast.Constant) or not isinstance(path_node.value, str):
        return None
    return ParsedRoute(
        method=method,
        path=path_node.value,
        handler=handler,
        file_path=file_path,
    )


def _calls_for_function(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    caller: str,
) -> list[CallEdge]:
    edges: list[CallEdge] = []
    for body_node in _walk_function_body(node.body):
        if isinstance(body_node, ast.Call):
            callee_name = _callee_name(body_node.func)
            if callee_name is not None:
                edges.append(CallEdge(caller=caller, callee_name=callee_name))
    return edges


def _walk_function_body(nodes: Iterable[ast.stmt]) -> Iterable[ast.AST]:
    for node in nodes:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            continue
        yield node
        yield from ast.iter_child_nodes(node)
        for child in ast.iter_child_nodes(node):
            if not isinstance(
                child,
                ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
            ):
                yield from _walk_children(child)


def _walk_children(node: ast.AST) -> Iterable[ast.AST]:
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            continue
        yield child
        yield from _walk_children(child)


def _callee_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _dedupe_calls(calls: list[CallEdge]) -> list[CallEdge]:
    seen: set[tuple[str, str]] = set()
    deduped: list[CallEdge] = []
    for call in calls:
        key = (call.caller, call.callee_name)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(call)
    return deduped
