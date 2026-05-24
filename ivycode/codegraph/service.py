from __future__ import annotations

import sqlite3
from collections import defaultdict, deque
from pathlib import Path

import aiosqlite
from pydantic import NonNegativeInt

from ivycode.codegraph.projection import CallEdge, ParsedModule, parse_python_source
from ivycode.codegraph.snapshot import (
    build_graph_snapshot,
    extract_terms,
    looks_like_route_query,
)
from ivycode.core.envelope import (
    FrameworkRoute,
    GraphSnapshot,
    ImpactReport,
    IvyBaseModel,
    SymbolBrief,
)


class CodeGraphStats(IvyBaseModel):
    indexed_files_count: NonNegativeInt
    symbols_count: NonNegativeInt
    routes_count: NonNegativeInt


class CodeGraphService:
    def __init__(self) -> None:
        self.project_root: Path | None = None
        self.db_path: Path | None = None
        self._db: aiosqlite.Connection | None = None

    async def boot(self, project_root: Path) -> None:
        root = project_root.resolve()
        graph_dir = root / ".ivycode"
        graph_dir.mkdir(parents=True, exist_ok=True)
        self.project_root = root
        self.db_path = graph_dir / "codegraph.sqlite"
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = sqlite3.Row
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute("PRAGMA foreign_keys=ON")
        await self._create_schema()

    async def shutdown(self) -> None:
        if self._db is None:
            return
        await self._db.close()
        self._db = None

    async def index(self, *, force: bool = False) -> CodeGraphStats:
        db = self._connection()
        files = list(self._iter_python_files())

        if force:
            await self._clear_index()
            await self._index_files(files)
            await db.commit()
            return await self.stats()

        for path in files:
            relative_path = self._relative_file_path(path)
            file_stat = path.stat()
            if await self._is_index_current(
                relative_path,
                file_stat.st_mtime,
                file_stat.st_size,
            ):
                continue
            await self.reindex_path(path)
        await db.commit()
        return await self.stats()

    async def reindex_path(self, path: Path) -> CodeGraphStats:
        db = self._connection()
        absolute_path = path.resolve()
        relative_path = self._relative_file_path(absolute_path)

        await self._delete_file(relative_path)
        if not absolute_path.exists():
            await db.commit()
            return await self.stats()

        module = self._parse_file(absolute_path)
        await self._insert_modules([module])
        await db.commit()
        return await self.stats()

    async def search_symbols(
        self,
        query: str,
        *,
        limit: int = 20,
    ) -> list[SymbolBrief]:
        db = self._connection()
        terms = extract_terms(query)
        if not terms and query.strip():
            terms = [query.strip().lower()]
        if not terms:
            return []

        clauses: list[str] = []
        params: list[object] = []
        for term in terms:
            pattern = f"%{term}%"
            clauses.append(
                "("
                "lower(s.name) LIKE ? OR "
                "lower(s.qualified_name) LIKE ? OR "
                "lower(s.signature) LIKE ? OR "
                "lower(coalesce(s.docstring_summary, '')) LIKE ?"
                ")"
            )
            params.extend([pattern, pattern, pattern, pattern])

        name_pattern = f"%{terms[0]}%"
        params.extend([name_pattern, name_pattern, limit])
        sql = f"""
            SELECT
                s.qualified_name,
                s.name,
                s.kind,
                s.file_path,
                s.line_start,
                s.line_end,
                s.signature,
                s.docstring_summary,
                (SELECT COUNT(DISTINCT c.caller)
                   FROM calls c
                  WHERE c.callee = s.qualified_name) AS callers_count,
                (SELECT COUNT(DISTINCT c.callee)
                   FROM calls c
                  WHERE c.caller = s.qualified_name) AS callees_count
            FROM symbols s
            WHERE {' AND '.join(clauses)}
            ORDER BY
                CASE WHEN lower(s.name) LIKE ? THEN 0 ELSE 1 END,
                CASE WHEN lower(s.qualified_name) LIKE ? THEN 0 ELSE 1 END,
                s.qualified_name
            LIMIT ?
        """
        async with db.execute(sql, params) as cursor:
            rows = await cursor.fetchall()
        return [_row_to_symbol(row) for row in rows]

    async def get_framework_routes(
        self,
        *,
        framework: str | None = None,
    ) -> list[FrameworkRoute]:
        db = self._connection()
        params: list[object] = []
        where = ""
        if framework is not None:
            where = "WHERE r.framework = ?"
            params.append(framework)
        sql = f"""
            SELECT
                r.method AS route_method,
                r.path AS route_path,
                r.framework AS route_framework,
                s.qualified_name,
                s.name,
                s.kind,
                s.file_path,
                s.line_start,
                s.line_end,
                s.signature,
                s.docstring_summary,
                (SELECT COUNT(DISTINCT c.caller)
                   FROM calls c
                  WHERE c.callee = s.qualified_name) AS callers_count,
                (SELECT COUNT(DISTINCT c.callee)
                   FROM calls c
                  WHERE c.caller = s.qualified_name) AS callees_count
            FROM routes r
            JOIN symbols s ON s.qualified_name = r.handler
            {where}
            ORDER BY r.path, r.method, r.handler
        """
        async with db.execute(sql, params) as cursor:
            rows = await cursor.fetchall()
        return [
            FrameworkRoute(
                method=_row_str(row, "route_method"),
                path=_row_str(row, "route_path"),
                handler=_row_to_symbol(row),
                framework=_row_str(row, "route_framework"),
            )
            for row in rows
        ]

    async def get_impact_radius(self, symbol: str) -> ImpactReport:
        target = await self._get_symbol(symbol)
        if target is None:
            raise KeyError(f"symbol not found: {symbol}")

        direct_callers = await self._callers_of(symbol)
        transitive_names = await self._transitive_callers_of(symbol)
        affected_symbols = await self._symbols_by_names(transitive_names)
        affected_files = sorted({caller.file_path for caller in affected_symbols})
        if target.file_path not in affected_files:
            affected_files.append(target.file_path)

        risk_score = min(
            1.0,
            (len(direct_callers) * 0.2) + (len(transitive_names) * 0.05),
        )
        return ImpactReport(
            target=target,
            direct_callers=direct_callers[:20],
            transitive_callers_count=len(transitive_names),
            affected_files=affected_files,
            risk_score=risk_score,
        )

    async def snapshot_for(
        self,
        user_query: str,
        *,
        max_tokens: int = 2000,
    ) -> GraphSnapshot:
        stats = await self.stats()
        symbols = await self.search_symbols(user_query, limit=30)
        routes = (
            await self.get_framework_routes()
            if looks_like_route_query(user_query)
            else []
        )
        return build_graph_snapshot(
            project_root=str(self._project_root()),
            indexed_files_count=stats.indexed_files_count,
            symbols=symbols,
            routes=routes,
            max_tokens=max_tokens,
        )

    async def stats(self) -> CodeGraphStats:
        indexed_files_count = await self._count("indexed_files")
        symbols_count = await self._count("symbols")
        routes_count = await self._count("routes")
        return CodeGraphStats(
            indexed_files_count=indexed_files_count,
            symbols_count=symbols_count,
            routes_count=routes_count,
        )

    async def _create_schema(self) -> None:
        db = self._connection()
        await db.executescript(
            """
            CREATE TABLE IF NOT EXISTS indexed_files (
                file_path TEXT PRIMARY KEY,
                mtime REAL NOT NULL,
                size INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS symbols (
                qualified_name TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                kind TEXT NOT NULL,
                file_path TEXT NOT NULL,
                line_start INTEGER NOT NULL,
                line_end INTEGER NOT NULL,
                signature TEXT NOT NULL,
                docstring_summary TEXT
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS symbols_fts USING fts5(
                qualified_name UNINDEXED,
                name,
                signature,
                docstring_summary
            );

            CREATE TABLE IF NOT EXISTS calls (
                caller TEXT NOT NULL,
                callee TEXT NOT NULL,
                PRIMARY KEY (caller, callee)
            );

            CREATE TABLE IF NOT EXISTS routes (
                method TEXT NOT NULL,
                path TEXT NOT NULL,
                handler TEXT NOT NULL,
                framework TEXT NOT NULL,
                file_path TEXT NOT NULL,
                PRIMARY KEY (method, path, handler)
            );
            """
        )
        await db.commit()

    async def _clear_index(self) -> None:
        db = self._connection()
        for table in ("indexed_files", "symbols", "symbols_fts", "calls", "routes"):
            await db.execute(f"DELETE FROM {table}")

    async def _index_files(self, files: list[Path]) -> None:
        modules = [self._parse_file(path) for path in files]
        await self._insert_modules(modules)

    async def _insert_modules(self, modules: list[ParsedModule]) -> None:
        db = self._connection()
        for module in modules:
            await self._delete_file(module.file_path)

        symbol_names = _symbol_names(modules)
        for module in modules:
            file_path = self._project_root() / module.file_path
            file_stat = file_path.stat()
            await db.execute(
                """
                INSERT INTO indexed_files (file_path, mtime, size)
                VALUES (?, ?, ?)
                ON CONFLICT(file_path) DO UPDATE SET
                    mtime = excluded.mtime,
                    size = excluded.size
                """,
                (module.file_path, file_stat.st_mtime, file_stat.st_size),
            )
            for symbol in module.symbols:
                await db.execute(
                    """
                    INSERT INTO symbols (
                        qualified_name,
                        name,
                        kind,
                        file_path,
                        line_start,
                        line_end,
                        signature,
                        docstring_summary
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        symbol.qualified_name,
                        _short_name(symbol.qualified_name),
                        symbol.kind,
                        symbol.file_path,
                        symbol.line_start,
                        symbol.line_end,
                        symbol.signature,
                        symbol.docstring_summary,
                    ),
                )
                await db.execute(
                    """
                    INSERT INTO symbols_fts (
                        qualified_name,
                        name,
                        signature,
                        docstring_summary
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        symbol.qualified_name,
                        _short_name(symbol.qualified_name),
                        symbol.signature,
                        symbol.docstring_summary or "",
                    ),
                )
            for route in module.routes:
                await db.execute(
                    """
                    INSERT OR REPLACE INTO routes (
                        method,
                        path,
                        handler,
                        framework,
                        file_path
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        route.method,
                        route.path,
                        route.handler,
                        route.framework,
                        route.file_path,
                    ),
                )

        db_symbols = await self._symbol_name_index()
        for name, qualified_names in symbol_names.items():
            db_symbols[name].extend(qualified_names)

        for module in modules:
            for call in module.calls:
                callee = _resolve_callee(call, db_symbols)
                await db.execute(
                    """
                    INSERT OR IGNORE INTO calls (caller, callee)
                    VALUES (?, ?)
                    """,
                    (call.caller, callee),
                )

    async def _delete_file(self, file_path: str) -> None:
        db = self._connection()
        async with db.execute(
            "SELECT qualified_name FROM symbols WHERE file_path = ?",
            (file_path,),
        ) as cursor:
            rows = await cursor.fetchall()
        qualified_names = [_row_str(row, "qualified_name") for row in rows]

        await db.execute("DELETE FROM indexed_files WHERE file_path = ?", (file_path,))
        await db.execute("DELETE FROM routes WHERE file_path = ?", (file_path,))
        await db.execute("DELETE FROM symbols WHERE file_path = ?", (file_path,))
        for qualified_name in qualified_names:
            await db.execute(
                "DELETE FROM symbols_fts WHERE qualified_name = ?",
                (qualified_name,),
            )
            await db.execute(
                "DELETE FROM calls WHERE caller = ? OR callee = ?",
                (qualified_name, qualified_name),
            )

    async def _is_index_current(self, file_path: str, mtime: float, size: int) -> bool:
        db = self._connection()
        async with db.execute(
            """
            SELECT 1
            FROM indexed_files
            WHERE file_path = ? AND mtime = ? AND size = ?
            """,
            (file_path, mtime, size),
        ) as cursor:
            row = await cursor.fetchone()
        return row is not None

    async def _symbol_name_index(self) -> defaultdict[str, list[str]]:
        db = self._connection()
        names: defaultdict[str, list[str]] = defaultdict(list)
        async with db.execute("SELECT qualified_name, name FROM symbols") as cursor:
            rows = await cursor.fetchall()
        for row in rows:
            names[_row_str(row, "name")].append(_row_str(row, "qualified_name"))
        return names

    async def _get_symbol(self, qualified_name: str) -> SymbolBrief | None:
        db = self._connection()
        async with db.execute(
            """
            SELECT
                s.qualified_name,
                s.name,
                s.kind,
                s.file_path,
                s.line_start,
                s.line_end,
                s.signature,
                s.docstring_summary,
                (SELECT COUNT(DISTINCT c.caller)
                   FROM calls c
                  WHERE c.callee = s.qualified_name) AS callers_count,
                (SELECT COUNT(DISTINCT c.callee)
                   FROM calls c
                  WHERE c.caller = s.qualified_name) AS callees_count
            FROM symbols s
            WHERE s.qualified_name = ?
            """,
            (qualified_name,),
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return None
        return _row_to_symbol(row)

    async def _callers_of(self, qualified_name: str) -> list[SymbolBrief]:
        names = await self._direct_caller_names(qualified_name)
        return await self._symbols_by_names(names)

    async def _direct_caller_names(self, qualified_name: str) -> list[str]:
        db = self._connection()
        async with db.execute(
            """
            SELECT DISTINCT caller
            FROM calls
            WHERE callee = ?
            ORDER BY caller
            """,
            (qualified_name,),
        ) as cursor:
            rows = await cursor.fetchall()
        return [_row_str(row, "caller") for row in rows]

    async def _transitive_callers_of(self, qualified_name: str) -> set[str]:
        seen: set[str] = set()
        frontier: deque[str] = deque([qualified_name])
        while frontier:
            current = frontier.popleft()
            for caller in await self._direct_caller_names(current):
                if caller in seen:
                    continue
                seen.add(caller)
                frontier.append(caller)
        return seen

    async def _symbols_by_names(
        self,
        qualified_names: set[str] | list[str],
    ) -> list[SymbolBrief]:
        symbols: list[SymbolBrief] = []
        for qualified_name in sorted(qualified_names):
            symbol = await self._get_symbol(qualified_name)
            if symbol is not None:
                symbols.append(symbol)
        return symbols

    async def _count(self, table: str) -> int:
        db = self._connection()
        async with db.execute(f"SELECT COUNT(*) AS count FROM {table}") as cursor:
            row = await cursor.fetchone()
        if row is None:
            return 0
        return int(_row_int(row, "count"))

    def _parse_file(self, path: Path) -> ParsedModule:
        relative_path = self._relative_file_path(path)
        return parse_python_source(
            source=path.read_text(encoding="utf-8"),
            file_path=relative_path,
            module_name=_module_name_for_path(Path(relative_path)),
        )

    def _iter_python_files(self) -> list[Path]:
        root = self._project_root()
        paths: list[Path] = []
        for path in root.rglob("*.py"):
            relative = path.relative_to(root)
            if _is_excluded(relative):
                continue
            paths.append(path)
        return sorted(paths)

    def _relative_file_path(self, path: Path) -> str:
        root = self._project_root()
        absolute_path = path.resolve()
        if not absolute_path.is_relative_to(root):
            raise ValueError(f"path is outside project root: {path}")
        return absolute_path.relative_to(root).as_posix()

    def _project_root(self) -> Path:
        if self.project_root is None:
            raise RuntimeError("CodeGraphService.boot() must be called first")
        return self.project_root

    def _connection(self) -> aiosqlite.Connection:
        if self._db is None:
            raise RuntimeError("CodeGraphService.boot() must be called first")
        return self._db


def _row_to_symbol(row: sqlite3.Row) -> SymbolBrief:
    return SymbolBrief(
        qualified_name=_row_str(row, "qualified_name"),
        kind=_row_str(row, "kind"),
        file_path=_row_str(row, "file_path"),
        line_start=_row_int(row, "line_start"),
        line_end=_row_int(row, "line_end"),
        signature=_row_str(row, "signature"),
        docstring_summary=_row_optional_str(row, "docstring_summary"),
        callers_count=_row_int(row, "callers_count"),
        callees_count=_row_int(row, "callees_count"),
    )


def _row_str(row: sqlite3.Row, key: str) -> str:
    return str(row[key])


def _row_optional_str(row: sqlite3.Row, key: str) -> str | None:
    value = row[key]
    if value is None:
        return None
    return str(value)


def _row_int(row: sqlite3.Row, key: str) -> int:
    return int(row[key])


def _symbol_names(modules: list[ParsedModule]) -> defaultdict[str, list[str]]:
    names: defaultdict[str, list[str]] = defaultdict(list)
    for module in modules:
        for symbol in module.symbols:
            names[_short_name(symbol.qualified_name)].append(symbol.qualified_name)
    return names


def _resolve_callee(call: CallEdge, symbol_names: defaultdict[str, list[str]]) -> str:
    matches = list(dict.fromkeys(symbol_names.get(call.callee_name, [])))
    if len(matches) == 1:
        return matches[0]
    local_match = _local_symbol_match(call.caller, call.callee_name, matches)
    if local_match is not None:
        return local_match
    return call.callee_name


def _local_symbol_match(
    caller: str,
    callee_name: str,
    matches: list[str],
) -> str | None:
    caller_module = ".".join(caller.split(".")[:-1])
    candidates = [
        match
        for match in matches
        if match == f"{caller_module}.{callee_name}"
        or match.startswith(f"{caller_module}.")
    ]
    if len(candidates) == 1:
        return candidates[0]
    return None


def _short_name(qualified_name: str) -> str:
    return qualified_name.rsplit(".", 1)[-1]


def _module_name_for_path(relative_path: Path) -> str:
    parts = list(relative_path.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    if not parts:
        return "__init__"
    return ".".join(parts)


def _is_excluded(relative_path: Path) -> bool:
    excluded = {
        ".git",
        ".ivycode",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "__pycache__",
    }
    return any(part in excluded for part in relative_path.parts)
