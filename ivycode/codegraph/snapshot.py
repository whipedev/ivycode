from __future__ import annotations

import re

from ivycode.core.envelope import FrameworkRoute, GraphSnapshot, SymbolBrief

_STOPWORDS = {
    "a",
    "an",
    "and",
    "by",
    "for",
    "from",
    "in",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
}

_ROUTE_TERMS = {
    "api",
    "delete",
    "endpoint",
    "get",
    "patch",
    "post",
    "put",
    "route",
    "ws",
}


def extract_terms(query: str) -> list[str]:
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", query)
    raw_terms = re.split(r"[^A-Za-z0-9]+", spaced)
    terms: list[str] = []
    for term in raw_terms:
        normalized = term.lower()
        if not normalized or normalized in _STOPWORDS:
            continue
        terms.append(normalized)
    return terms


def looks_like_route_query(query: str) -> bool:
    if "/" in query:
        return True
    return any(term in _ROUTE_TERMS for term in extract_terms(query))


def estimate_symbol_tokens(symbol: SymbolBrief) -> int:
    text = " ".join(
        part
        for part in (
            symbol.qualified_name,
            symbol.kind,
            symbol.file_path,
            symbol.signature,
            symbol.docstring_summary or "",
        )
        if part
    )
    return max(1, len(re.findall(r"[A-Za-z0-9_]+", text)) + 4)


def _estimate_route_tokens(route: FrameworkRoute) -> int:
    return estimate_symbol_tokens(route.handler) + 4


def build_graph_snapshot(
    *,
    project_root: str,
    indexed_files_count: int,
    symbols: list[SymbolBrief],
    routes: list[FrameworkRoute],
    max_tokens: int,
) -> GraphSnapshot:
    token_budget = max(1, max_tokens)
    selected_symbols: list[SymbolBrief] = []
    selected_routes: list[FrameworkRoute] = []
    estimated_tokens = 0

    for symbol in symbols[:30]:
        symbol_tokens = estimate_symbol_tokens(symbol)
        if selected_symbols and estimated_tokens + symbol_tokens > token_budget:
            continue
        if not selected_symbols and symbol_tokens > token_budget:
            break
        selected_symbols.append(symbol)
        estimated_tokens += symbol_tokens

    for route in routes[:20]:
        route_tokens = _estimate_route_tokens(route)
        if estimated_tokens + route_tokens > token_budget:
            continue
        selected_routes.append(route)
        estimated_tokens += route_tokens

    return GraphSnapshot(
        project_root=project_root,
        indexed_files_count=indexed_files_count,
        relevant_symbols=selected_symbols,
        relevant_routes=selected_routes,
        estimated_tokens=max(1, estimated_tokens),
    )
