from __future__ import annotations

from ivycode.codegraph.projection import parse_python_source

SOURCE = '''
from fastapi import APIRouter

router = APIRouter()

class AuthService:
    """Authentication service."""

    def authenticate_user(self, token: str) -> bool:
        """Validate token."""
        return verify_token(token)


def verify_token(token: str) -> bool:
    return bool(token)


@router.post("/login")
async def login(token: str) -> bool:
    return AuthService().authenticate_user(token)
'''


def test_parse_python_source_extracts_symbols_and_routes() -> None:
    module = parse_python_source(
        source=SOURCE,
        file_path="app/auth.py",
        module_name="app.auth",
    )

    by_name = {symbol.qualified_name: symbol for symbol in module.symbols}

    assert by_name["app.auth.AuthService"].kind == "class"
    assert (
        by_name["app.auth.AuthService"].docstring_summary
        == "Authentication service."
    )
    assert by_name["app.auth.AuthService.authenticate_user"].kind == "method"
    assert by_name["app.auth.AuthService.authenticate_user"].signature == (
        "def authenticate_user(self, token: str) -> bool"
    )
    assert by_name["app.auth.verify_token"].kind == "function"
    assert by_name["app.auth.login"].signature == "async def login(token: str) -> bool"

    assert len(module.routes) == 1
    assert module.routes[0].method == "POST"
    assert module.routes[0].path == "/login"
    assert module.routes[0].handler == "app.auth.login"


def test_parse_python_source_extracts_call_edges() -> None:
    module = parse_python_source(
        source=SOURCE,
        file_path="app/auth.py",
        module_name="app.auth",
    )

    edges = {(edge.caller, edge.callee_name) for edge in module.calls}

    assert ("app.auth.AuthService.authenticate_user", "verify_token") in edges
    assert ("app.auth.login", "authenticate_user") in edges
