from __future__ import annotations

import asyncio
from pathlib import Path

from ivycode.codegraph.service import CodeGraphService


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_codegraph_indexes_searches_routes_and_impact(tmp_path: Path) -> None:
    write(
        tmp_path / "app" / "auth.py",
        """
def verify_token(token: str) -> bool:
    return bool(token)

def authenticate_user(token: str) -> bool:
    return verify_token(token)
""",
    )
    write(
        tmp_path / "app" / "api.py",
        """
from fastapi import APIRouter
from app.auth import authenticate_user

router = APIRouter()

@router.post("/login")
async def login(token: str) -> bool:
    return authenticate_user(token)
""",
    )

    async def run() -> None:
        service = CodeGraphService()
        await service.boot(tmp_path)
        stats = await service.index(force=True)

        assert stats.indexed_files_count == 2
        assert stats.symbols_count == 3
        assert stats.routes_count == 1

        matches = await service.search_symbols("authenticate", limit=5)
        assert [match.qualified_name for match in matches] == [
            "app.auth.authenticate_user"
        ]

        routes = await service.get_framework_routes()
        assert routes[0].method == "POST"
        assert routes[0].path == "/login"
        assert routes[0].handler.qualified_name == "app.api.login"

        impact = await service.get_impact_radius("app.auth.authenticate_user")
        assert impact.target.qualified_name == "app.auth.authenticate_user"
        assert [caller.qualified_name for caller in impact.direct_callers] == [
            "app.api.login"
        ]
        assert "app/api.py" in impact.affected_files
        assert impact.risk_score > 0

        await service.shutdown()

    asyncio.run(run())


def test_codegraph_reindex_path_updates_symbols(tmp_path: Path) -> None:
    target = tmp_path / "pkg" / "module.py"
    write(target, "def old_name() -> None:\n    return None\n")

    async def run() -> None:
        service = CodeGraphService()
        await service.boot(tmp_path)
        await service.reindex_path(target)
        assert [s.qualified_name for s in await service.search_symbols("old_name")] == [
            "pkg.module.old_name"
        ]

        write(target, "def new_name() -> None:\n    return None\n")
        await service.reindex_path(target)

        assert await service.search_symbols("old_name") == []
        assert [s.qualified_name for s in await service.search_symbols("new_name")] == [
            "pkg.module.new_name"
        ]
        await service.shutdown()

    asyncio.run(run())
