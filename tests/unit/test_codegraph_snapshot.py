from __future__ import annotations

from ivycode.codegraph.snapshot import (
    build_graph_snapshot,
    estimate_symbol_tokens,
    extract_terms,
    looks_like_route_query,
)
from ivycode.core.envelope import GraphSnapshot, SymbolBrief


def symbol(name: str) -> SymbolBrief:
    return SymbolBrief(
        qualified_name=f"app.auth.{name}",
        kind="function",
        file_path="app/auth.py",
        line_start=1,
        line_end=3,
        signature=f"def {name}() -> None",
        callers_count=1,
        callees_count=0,
    )


def test_extract_terms_keeps_code_like_identifiers() -> None:
    assert extract_terms("Refactor authenticateUser in auth/login API") == [
        "refactor",
        "authenticate",
        "user",
        "auth",
        "login",
        "api",
    ]


def test_route_query_detection() -> None:
    assert looks_like_route_query("fix POST /login endpoint")
    assert looks_like_route_query("show API route for auth")
    assert not looks_like_route_query("rename helper function")


def test_build_graph_snapshot_respects_budget() -> None:
    symbols = [symbol("authenticate_user"), symbol("verify_token")]
    snapshot = build_graph_snapshot(
        project_root="/repo",
        indexed_files_count=10,
        symbols=symbols,
        routes=[],
        max_tokens=estimate_symbol_tokens(symbols[0]) + 1,
    )

    assert isinstance(snapshot, GraphSnapshot)
    assert snapshot.project_root == "/repo"
    assert [s.qualified_name for s in snapshot.relevant_symbols] == [
        "app.auth.authenticate_user"
    ]
    assert snapshot.estimated_tokens > 0
