# PROMPT-SPEC: «ivycode» — Multi-Agent CLI Platform with Semantic CodeGraph

**Целевая модель-исполнитель:** GPT-5.5 xhigh
**Роль исполнителя:** Senior Python Architect + CLI/UX Engineer
**Режим:** Production-grade, zero-placeholder, full file-tree delivery
**Стиль кода:** PEP 8 + PEP 484 (strict typing), `from __future__ import annotations`, Python 3.11+
**Запрещено:** TODO, `pass`-заглушки, mock-ответы, «упрощённые версии для демо», использование `print()`, `requests`, `time.sleep` в async-коде.

> **Директива исполнителю:** Этот документ — единственный источник истины. Если что-то не описано — выводи из принципов:
> (а) асинхронность по умолчанию,
> (б) Pydantic v2 как контракт,
> (в) Rich как единственный канал вывода,
> (г) CodeGraph как первичный источник контекста для LLM,
> (д) JSON Schema через Pydantic как единственный способ обмена структурированными данными между агентами.

---

## 0. Глоссарий и инварианты

| Термин | Определение |
|---|---|
| **Provider** | Адаптер к одному LLM API (Anthropic, OpenAI, Google) |
| **Agent** | Логическая сущность с системным промптом, набором инструментов и стратегией принятия решений |
| **SubAgent** | Специализированный Agent, подчинённый Router-у |
| **Skill** | Атомарный Python-callable, экспонируемый как tool в LLM через JSON Schema |
| **Plugin** | Группа Skill-ов с собственным namespace и lifecycle |
| **CodeGraph** | Локальный семантический индекс проекта (SQLite + FTS5) |
| **Envelope** | Pydantic-обёртка любого межслойного сообщения с метаданными об агенте/модели/времени |
| **TokenBudget** | Жёсткий контракт: сколько токенов разрешено отправить в LLM за один шаг плана |

**Инварианты системы (НЕ нарушать):**

1. Ни один SubAgent не имеет прямого доступа к диску. Только через Skills `read_file`, `write_file` и через CodeGraph-инструменты.
2. Router НИКОГДА не отправляет в подагент сырой ввод пользователя без обогащения данными из CodeGraph.
3. Любой ответ LLM, который должен распарситься в структуру, валидируется через Pydantic `model_validate_json` с `strict=True`. Невалидный ответ → автоматический retry с инструкцией «верни строго по схеме», максимум 2 попытки.
4. Весь stdout/stderr идёт ТОЛЬКО через `rich.console.Console`. `logging` настроен на `RichHandler`.
5. Каждая операция, длящаяся > 50 мс, обёрнута в `Live` или `Status`.
6. Каждое `Message` несёт `CallerMeta` — без неё объект не должен существовать.

---

## 1. Архитектура и паттерны

### 1.1. Структура репозитория

```
ivycode/
├── pyproject.toml                  # uv backend, ruff, pytest, mypy --strict
├── README.md
├── ivycode/
│   ├── __init__.py
│   ├── __main__.py                 # python -m ivycode
│   ├── cli/
│   │   ├── __init__.py
│   │   ├── app.py                  # Typer app, root commands
│   │   ├── commands/
│   │   │   ├── chat.py             # ivycode chat
│   │   │   ├── plan.py             # ivycode plan <task>
│   │   │   ├── index.py            # ivycode index (force reindex)
│   │   │   ├── doctor.py           # ivycode doctor (диагностика)
│   │   │   └── plugins.py          # ivycode plugins list/install
│   │   └── repl.py                 # Интерактивный режим с prompt_toolkit
│   │
│   ├── core/
│   │   ├── settings.py             # pydantic-settings, .env, ~/.ivycode/config.toml
│   │   ├── runtime.py              # Composition Root: provider_registry, skills, codegraph, ui
│   │   ├── envelope.py             # Pydantic-обёртки сообщений (см. §2)
│   │   ├── event_bus.py            # AsyncIO Pub/Sub (Observer)
│   │   ├── errors.py               # Иерархия исключений
│   │   └── token_budget.py         # Подсчёт через tiktoken/anthropic-tokenizer, hard limits
│   │
│   ├── providers/
│   │   ├── base.py                 # ABC LLMProvider
│   │   ├── factory.py              # Abstract Factory + Registry
│   │   ├── anthropic_provider.py
│   │   ├── openai_provider.py
│   │   ├── google_provider.py
│   │   └── stream.py               # Унифицированные StreamEvent-ы
│   │
│   ├── agents/
│   │   ├── base.py                 # Agent ABC, AgentResult
│   │   ├── mediator.py             # AgentMediator (Mediator pattern)
│   │   ├── router.py               # RouterAgent (Planner)
│   │   ├── subagents/
│   │   │   ├── architect.py
│   │   │   ├── refactorer.py
│   │   │   ├── tester.py
│   │   │   └── documenter.py
│   │   ├── prompts/                # Markdown-файлы системных промптов
│   │   │   ├── router.md
│   │   │   ├── architect.md
│   │   │   ├── refactorer.md
│   │   │   ├── tester.md
│   │   │   └── documenter.md
│   │   └── validators.py           # JSON-Schema enforcement + auto-retry
│   │
│   ├── codegraph/
│   │   ├── __init__.py             # Re-export public API из библиотеки CodeGraph
│   │   ├── service.py              # Фасад: index(), search_symbols(), get_impact_radius()
│   │   ├── watcher.py              # watchdog + debounce
│   │   ├── snapshot.py             # Сериализация контекста для LLM (token-efficient)
│   │   └── projection.py           # Конвертация результатов графа → SymbolBrief/ImpactReport
│   │
│   ├── skills/
│   │   ├── base.py                 # Skill ABC, @skill декоратор
│   │   ├── registry.py             # SkillRegistry, JSON-schema генератор
│   │   ├── builtins/
│   │   │   ├── fs.py               # read_file, write_file (gated через CodeGraph)
│   │   │   ├── shell.py            # run_command (sandboxed)
│   │   │   ├── web.py              # fetch, search (httpx + DDG)
│   │   │   └── graph.py            # search_symbols, get_impact_radius, get_framework_routes
│   │   └── loader.py               # Динамическая загрузка плагинов из ~/.ivycode/plugins/*
│   │
│   ├── orchestration/
│   │   ├── parallel.py             # asyncio.TaskGroup для мультимодельного запроса
│   │   ├── scheduler.py            # FanOut / FanIn / Race
│   │   └── retry.py                # Tenacity-обёртки с экспоненциальным backoff
│   │
│   ├── ui/
│   │   ├── theme.py                # Цветовая палитра (см. §4)
│   │   ├── console.py              # Singleton Rich Console
│   │   ├── layout.py               # Сборка Layout (header/body/footer)
│   │   ├── panels/
│   │   │   ├── model_panel.py      # ОДИН блок стрима для ОДНОЙ модели
│   │   │   ├── activity_panel.py   # Лента агентов
│   │   │   ├── tool_panel.py       # Tree-лог вызовов инструментов
│   │   │   └── status_bar.py       # Токены / стоимость / latency
│   │   ├── widgets/
│   │   │   ├── spinner.py          # Кастомные spinner-presets
│   │   │   ├── code.py             # Подсветка диффов
│   │   │   └── markdown.py
│   │   └── live_session.py         # Контекстный менеджер для Rich.Live
│   │
│   └── persistence/
│       ├── history.py              # JSONL диалогов в ~/.ivycode/history/
│       └── cache.py                # diskcache для LLM-кеша по hash(prompt+model)
│
└── tests/
    ├── unit/
    ├── integration/
    └── fixtures/
```

### 1.2. Применяемые паттерны (обязательные)

| Слой | Паттерн | Где |
|---|---|---|
| `providers/` | **Abstract Factory + Registry** | `ProviderFactory.create("anthropic", model="claude-opus-4-7")`. Регистрация декоратором `@register_provider("anthropic")`. |
| `agents/` | **Mediator** | `AgentMediator` — единственная точка, через которую SubAgent-ы общаются. Прямые ссылки агент↔агент запрещены. |
| `skills/` | **Command + Registry** | Каждый Skill — Command-объект. Реестр генерирует JSON Schema под каждый провайдер в его нативном формате. |
| `orchestration/` | **Fan-out / Fan-in** | `ParallelOrchestrator.dispatch(prompt, providers=[...])` → `asyncio.TaskGroup`. |
| `ui/` | **Observer** | UI подписывается на `EventBus`. Агенты публикуют `AgentEvent`, провайдеры — `StreamEvent`. |
| `codegraph/service.py` | **Facade** | Прячет внутренности библиотеки CodeGraph за стабильным API. |
| `core/runtime.py` | **Composition Root** | Единственная точка сборки зависимостей (без DI-фреймворка). |
| `persistence/cache.py` | **Decorator** | `@cached_provider_call` оборачивает `LLMProvider.send_request`. |

### 1.3. Поток данных (happy path)

```
CLI input
  → Runtime.create_session()
  → RouterAgent.handle(user_input)
      → CodeGraphService.snapshot_for(query)             # §3
      → RouterAgent.plan(enriched_context) → ExecutionPlan
      → Mediator.dispatch(plan.steps)
          → SubAgent.execute(step)
              → LLMProvider.stream(...)                  # параллельно если step.parallel=True
              → Skill.invoke(...) при tool_use
      → Mediator.aggregate(results) → FinalAnswer
  → UI.render_final(FinalAnswer)
```

### 1.4. Конкурентная модель

- Единый `asyncio` event loop, запускаемый `anyio.run` (для совместимости с trio-стайл бэкендами).
- Сетевой I/O — только `httpx.AsyncClient` (один на провайдер, переиспользуемый через `Runtime.http`).
- Файловый I/O — `aiofiles` для write; чтение мелких файлов допускается синхронно, если строго < 4 KB.
- Watchdog работает в отдельном потоке, события транслируются в loop через `asyncio.run_coroutine_threadsafe`.

#### 1.4.1. SQLite — single-writer thread + aiosqlite read pool

**Запрещено:** оборачивать общий `sqlite3.Connection` в `asyncio.to_thread`. ThreadPoolExecutor отдаёт задачи произвольным воркерам → `ProgrammingError` / `database is locked` / повреждение prepared-statement cache.

**Архитектура CodeGraph storage:**

```
┌──────────────────────────────────────────────────────────────┐
│  asyncio event loop                                          │
│   ├── readers (any coroutine) ──► aiosqlite pool (size=4)    │
│   │                                 each conn lives in its   │
│   │                                 own dedicated thread     │
│   └── writers (any coroutine) ──► WriteQueue (asyncio.Queue) │
│                                     │                        │
│  ┌──────────────────────────────────▼───────────────────┐    │
│  │  WriterThread (single OS thread, owns ONE conn)      │    │
│  │   loop.call_soon_threadsafe(future.set_result, ...)  │    │
│  └──────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
```

Контракт:

```python
class SqliteWriter:
    def __init__(self, db_path: Path) -> None:
        self._queue: queue.Queue[_WriteJob | None] = queue.Queue()
        self._thread = threading.Thread(target=self._run, daemon=True, name="ivycode-sqlite-writer")
        self._loop = asyncio.get_running_loop()

    def start(self) -> None: self._thread.start()

    async def execute(self, sql: str, params: tuple[object, ...] = ()) -> int:
        fut: asyncio.Future[int] = self._loop.create_future()
        self._queue.put(_WriteJob(sql=sql, params=params, future=fut, many=False))
        return await fut

    async def executemany(self, sql: str, rows: Sequence[tuple[object, ...]]) -> int:
        fut: asyncio.Future[int] = self._loop.create_future()
        self._queue.put(_WriteJob(sql=sql, params=rows, future=fut, many=True))
        return await fut

    async def transaction(self, ops: Sequence[tuple[str, tuple[object, ...]]]) -> None:
        fut: asyncio.Future[None] = self._loop.create_future()
        self._queue.put(_TxJob(ops=ops, future=fut))
        return await fut

    def _run(self) -> None:
        conn = sqlite3.connect(self._db_path, isolation_level=None, check_same_thread=True)
        self._apply_pragmas(conn)
        while (job := self._queue.get()) is not None:
            try:
                result = job.execute(conn)
                self._loop.call_soon_threadsafe(job.future.set_result, result)
            except BaseException as exc:
                self._loop.call_soon_threadsafe(job.future.set_exception, exc)
        conn.close()
```

**Обязательные PRAGMA для каждого коннекта (reader и writer):**

```sql
PRAGMA journal_mode = WAL;          -- параллельные readers + один writer
PRAGMA synchronous = NORMAL;        -- безопасно при WAL, в 3-5× быстрее FULL
PRAGMA temp_store = MEMORY;
PRAGMA mmap_size = 268435456;       -- 256 MB
PRAGMA busy_timeout = 5000;         -- 5s ожидание lock
PRAGMA cache_size = -65536;         -- 64 MB страничный кеш
PRAGMA foreign_keys = ON;
```

**Read-pool на `aiosqlite`:**

```python
class SqliteReadPool:
    def __init__(self, db_path: Path, size: int = 4) -> None:
        self._db_path = db_path
        self._size = size
        self._pool: asyncio.Queue[aiosqlite.Connection] = asyncio.Queue(maxsize=size)

    async def boot(self) -> None:
        for _ in range(self._size):
            conn = await aiosqlite.connect(self._db_path)
            await self._apply_pragmas(conn)
            conn.row_factory = aiosqlite.Row
            await self._pool.put(conn)

    @asynccontextmanager
    async def acquire(self) -> AsyncIterator[aiosqlite.Connection]:
        conn = await self._pool.get()
        try: yield conn
        finally: await self._pool.put(conn)
```

**Правила использования:**
- Все SELECT/FTS5 → через `read_pool.acquire()`.
- Все INSERT/UPDATE/DELETE/DDL → через `SqliteWriter.execute*` / `transaction()`.
- Reindex одного файла = один `writer.transaction([...])`, чтобы апдейт был атомарным.
- Никаких прямых вызовов `sqlite3.connect` ни в одном другом модуле.

---

## 2. Pydantic v2 — контракты

> Все модели наследуют `BaseModel` с `model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)`.
> Все Enum-ы — `StrEnum`. Все datetime — UTC-aware.

### 2.1. Идентификаторы и метаданные

```python
from __future__ import annotations
from datetime import datetime, timezone
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID, uuid4
from pydantic import BaseModel, ConfigDict, Field, PositiveInt, NonNegativeFloat, model_validator

class Role(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"

class ProviderName(StrEnum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GOOGLE = "google"

class AgentName(StrEnum):
    ROUTER = "router"
    ARCHITECT = "architect"
    REFACTORER = "refactorer"
    TESTER = "tester"
    DOCUMENTER = "documenter"

class ModelRef(BaseModel):
    model_config = ConfigDict(frozen=True)
    provider: ProviderName
    model_id: str                          # "claude-opus-4-7", "gpt-5.5-xhigh", "gemini-2.5-pro"
    display_name: str                      # для UI: "Claude Opus 4.7"

class UsageMetrics(BaseModel):
    input_tokens: PositiveInt
    output_tokens: PositiveInt
    cached_input_tokens: int = 0
    cost_usd: NonNegativeFloat
    latency_ms: PositiveInt

class CallerMeta(BaseModel):
    """Полная цепочка вызова: какой агент → какой провайдер → какая модель → какой инструмент."""
    trace_id: UUID = Field(default_factory=uuid4)
    span_id: UUID = Field(default_factory=uuid4)
    parent_span_id: UUID | None = None
    agent: AgentName
    model: ModelRef
    initiated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    tool_name: str | None = None           # заполняется когда message — результат tool_call
```

### 2.2. Сообщения и стрим-события

```python
class ToolCall(BaseModel):
    id: str
    name: str
    arguments: dict[str, object]

class ToolResult(BaseModel):
    tool_call_id: str
    success: bool
    payload: dict[str, object] | str
    error: str | None = None

class Message(BaseModel):
    """Универсальный envelope. ВСЁ ходит между слоями только через него."""
    id: UUID = Field(default_factory=uuid4)
    role: Role
    content: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    tool_result: ToolResult | None = None
    meta: CallerMeta
    usage: UsageMetrics | None = None      # заполняется только на финальном message от провайдера

class StreamEvent(BaseModel):
    """Унифицированное событие потока от любого провайдера."""
    kind: Literal["delta", "tool_call_start", "tool_call_args_delta",
                  "tool_call_end", "stop", "error"]
    text_delta: str | None = None
    tool_call: ToolCall | None = None
    args_delta: str | None = None          # для постепенной сборки JSON аргументов tool_use
    meta: CallerMeta
    final_usage: UsageMetrics | None = None
    error_message: str | None = None
```

### 2.3. План агента-планировщика (строгий выход Router-а)

```python
class StepKind(StrEnum):
    GRAPH_QUERY = "graph_query"            # запрос к CodeGraph, НЕ к LLM
    SUBAGENT = "subagent"
    PARALLEL_COMPARE = "parallel_compare"  # та же задача в N провайдеров
    AGGREGATE = "aggregate"

class GraphQuery(BaseModel):
    method: Literal["search_symbols", "get_impact_radius", "get_framework_routes"]
    arguments: dict[str, str | int]

class SubAgentDirective(BaseModel):
    agent: AgentName
    instructions: Annotated[str, Field(min_length=20)]
    inputs: dict[str, object]              # обязательно подмножество результатов прошлых шагов по id
    allowed_skills: list[str] = Field(default_factory=list)
    token_budget: PositiveInt = 8000
    expected_output_schema: dict[str, object] | None = None   # JSON Schema, передаётся как Structured Output

class ParallelCompareDirective(BaseModel):
    providers: list[ModelRef] = Field(min_length=2, max_length=4)
    prompt_template: str
    rubric: str                            # критерии последующего выбора лучшего ответа

class PlanStep(BaseModel):
    id: str = Field(pattern=r"^step_\d{2}$")
    kind: StepKind
    rationale: Annotated[str, Field(min_length=10, max_length=400)]
    depends_on: list[str] = Field(default_factory=list)
    graph_query: GraphQuery | None = None
    subagent: SubAgentDirective | None = None
    parallel_compare: ParallelCompareDirective | None = None
    timeout_s: PositiveInt = 60

    @model_validator(mode="after")
    def _exactly_one_payload(self) -> "PlanStep":
        payloads = [self.graph_query, self.subagent, self.parallel_compare]
        if sum(p is not None for p in payloads) != 1:
            raise ValueError("PlanStep must carry exactly one payload matching its kind")
        return self

class ExecutionPlan(BaseModel):
    """Этот объект Router возвращает СТРОГО как structured output LLM."""
    summary: Annotated[str, Field(min_length=20, max_length=600)]
    risk_level: Literal["low", "medium", "high"]
    estimated_total_tokens: PositiveInt
    steps: list[PlanStep] = Field(min_length=1, max_length=12)
    final_aggregator: AgentName | None = None
```

### 2.4. Результаты исполнения

```python
class StepResult(BaseModel):
    step_id: str
    success: bool
    output: dict[str, object] | str
    usage: UsageMetrics | None = None
    error: str | None = None
    duration_ms: PositiveInt

class SessionTranscript(BaseModel):
    session_id: UUID
    started_at: datetime
    plan: ExecutionPlan
    step_results: list[StepResult]
    final_message: Message
    total_usage: UsageMetrics
```

### 2.5. CodeGraph-проекции (компактные DTO для LLM)

```python
class SymbolBrief(BaseModel):
    """Минимально-достаточное описание символа для LLM. Никаких полных тел функций."""
    qualified_name: str                    # "app.auth.login.authenticate_user"
    kind: Literal["function", "class", "method", "route", "constant"]
    file_path: str                         # относительно корня репо
    line_start: PositiveInt
    line_end: PositiveInt
    signature: str                         # def authenticate_user(req: Request) -> User
    docstring_summary: str | None = None   # первая строка docstring
    callers_count: int
    callees_count: int

class ImpactReport(BaseModel):
    target: SymbolBrief
    direct_callers: list[SymbolBrief] = Field(max_length=20)
    transitive_callers_count: int
    affected_files: list[str]
    risk_score: NonNegativeFloat          # 0..1

class FrameworkRoute(BaseModel):
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE", "WS"]
    path: str
    handler: SymbolBrief
    framework: Literal["fastapi", "django", "flask", "express", "fastify", "rails"]

class GraphSnapshot(BaseModel):
    """Контекст, который Router передаёт в LLM ВМЕСТО сырых файлов."""
    project_root: str
    indexed_files_count: int
    relevant_symbols: list[SymbolBrief] = Field(max_length=30)
    relevant_routes: list[FrameworkRoute] = Field(default_factory=list, max_length=20)
    estimated_tokens: PositiveInt
```

---

## 3. Интеграция CodeGraph (ядро экономии токенов)

### 3.1. Жизненный цикл

```
ivycode chat (cwd=$REPO)
  1. CodeGraphService.boot(project_root):
        - Открывает/создаёт .ivycode/codegraph.sqlite
        - Если БД пустая ИЛИ mtime индекса < mtime самого свежего файла:
              запускает фоновый full_index() c прогресс-баром Rich
        - Стартует FileWatcher (watchdog) с debounce 300 ms
  2. Watcher на каждое FS-событие:
        - Ставит файл в очередь reindex_queue (asyncio.Queue)
        - Воркер берёт батч (до 50 файлов), парсит AST, апдейтит граф транзакционно
  3. На каждый запрос Router-а:
        - CodeGraphService.snapshot_for(user_query) → GraphSnapshot
        - Snapshot вкладывается в системный промпт Router-а
```

### 3.2. Алгоритм построения Snapshot (Token-Saving Logic)

Это сердце экономии токенов. Псевдокод:

```python
async def snapshot_for(self, query: str, max_tokens: int = 2_000) -> GraphSnapshot:
    # Шаг 1: извлечь кандидатов-термины из запроса
    terms = self._extract_terms(query)                       # NLP-минимум: split + stopwords + camelCase
    # Шаг 2: FTS5-поиск по символам, ранжирование по BM25
    raw_symbols = await self._fts_search(terms, limit=80)
    # Шаг 3: для top-5 символов посчитать impact, чтобы отфильтровать «листья»
    scored = []
    for s in raw_symbols[:5]:
        impact = await self.get_impact_radius(s.qualified_name)
        scored.append((s, impact.risk_score))
    # Шаг 4: добавить релевантные роуты, если query пахнет «эндпоинтом» или «API»
    routes = []
    if self._looks_like_route_query(query):
        routes = await self.get_framework_routes_matching(terms, limit=15)
    # Шаг 5: жадно заполняем snapshot, не превышая бюджет токенов
    snapshot = GraphSnapshot(
        project_root=self.root,
        indexed_files_count=await self._count_files(),
        relevant_symbols=[],
        relevant_routes=routes,
        estimated_tokens=0,
    )
    used = self._estimate_tokens(routes)
    for sym, _ in sorted(scored, key=lambda x: -x[1]):
        cost = self._estimate_tokens([sym])
        if used + cost > max_tokens:
            break
        snapshot.relevant_symbols.append(sym)
        used += cost
    snapshot.estimated_tokens = used
    return snapshot
```

### 3.3. Как Router использует CodeGraph

Router НЕ имеет инструмента «прочитай файл». Его системный промпт (§5) явно требует:

1. Сначала вызвать `search_symbols(query=...)` для всех ключевых терминов задачи.
2. Для каждого подозреваемого «эпицентра» — вызвать `get_impact_radius(symbol=...)`.
3. На основании полученных `SymbolBrief` сформировать `SubAgentDirective.inputs`, где вместо полного кода передаются только `qualified_name` + `file_path:line_start-line_end`.
4. SubAgent при необходимости расширит контекст через Skill `read_file(file_path, line_start, line_end)` — но только в пределах указанного диапазона (Skill валидирует).

**Результат экономии:** вместо отправки 30 КБ исходников в LLM, Router отправляет ~1–2 КБ структурированных `SymbolBrief` и точечно дочитывает только нужные диапазоны строк. На типичном репозитории это даёт 30–40% сокращения input-tokens.

### 3.4. Контракт фасада

```python
class CodeGraphService(Protocol):
    async def boot(self, project_root: Path) -> None: ...
    async def reindex_path(self, path: Path) -> None: ...
    async def search_symbols(self, query: str, *, limit: int = 20) -> list[SymbolBrief]: ...
    async def get_impact_radius(self, symbol: str) -> ImpactReport: ...
    async def get_framework_routes(self, *, framework: str | None = None) -> list[FrameworkRoute]: ...
    async def snapshot_for(self, user_query: str, *, max_tokens: int = 2_000) -> GraphSnapshot: ...
    async def shutdown(self) -> None: ...
```

---

## 4. UX/UI спецификация (Rich)

### 4.1. Визуальный стиль: «Cyberpunk × Quiet Luxury»

| Элемент | Значение |
|---|---|
| Фон | `#0B0D12` (near-black, чуть холоднее графита) |
| Основной текст | `#E6E6E6` |
| Акцент (главный) | `#7CFFB2` (мятно-неоновый) |
| Акцент (вторичный) | `#A78BFA` (электро-фиолет) |
| Тревога | `#FF6B6B` |
| Тонкие линии границ | `#2A2F3A` (rounded box-drawing) |
| Шрифт-эмфаза | bold + italic для имён агентов, dim для timestamp |
| Бордюры панелей | `box.ROUNDED` или `box.HEAVY_HEAD` для активной панели |
| Spinner | `dots12` или кастомный `▰▱▰▱▰▱` (см. §4.5) |
| Иконография | Только Unicode-глифы; никаких эмодзи (кроме отдельной «celebration»-зоны) |

Префиксы лейблов в стиле «brackets»: `╭─[ ROUTER ]──`, `╭─[ CLAUDE OPUS 4.7 ]──`.

### 4.2. Композиция Layout — единый чат-фид

Модели НЕ делятся на колонки. Они выступают «спикерами» в одном вертикальном фиде, как в групповом чате. Параллельный стрим = N соседних `MessagePanel`-ей, растущих одновременно. Это естественнее для чтения длинных ответов с кодом и не режет ширину терминала.

```
┌──────────────────  ivycode  · session 7f3a · cost $0.0142 · in 1,204 / out 318  ──┐
│ HEADER                                                                            │
├──────────────────────────────────────────────────┬────────────────────────────────┤
│  CHAT FEED  (scrollable)                         │  SIDE (ratio=1)                │
│                                                  │  ╭─[ ACTIVITY ]─────────────╮  │
│  ╭─[ ROUTER · 14:32:01 ]────────────── 412ms ─╮  │  │ ▰▱ router   planning…    │  │
│  │ Plan ready: 4 steps · risk=low             │  │  │ ✓  graph    snapshot     │  │
│  ╰─────────────────────────────────────────────╯  │  │ ▰▱ tester   gen spec     │  │
│                                                  │  ╰──────────────────────────╯  │
│  ▌ ◆  CLAUDE OPUS 4.7         14:32:02 · ✓ done  │  ╭─[ TOOL CALLS ]───────────╮  │
│  ▌  ответ Claude в полную ширину фида, никакого │  │ router                    │  │
│  ▌  30-символьного окна. Код подсвечен Syntax.  │  │  └─ search_symbols("…")   │  │
│  ▌  in 1,204 · out 318 · TTFB 412ms · $0.0042   │  │      └─ 3 matches         │  │
│                                                  │  ╰──────────────────────────╯  │
│  ▌ ▲  GPT-5.5 XHIGH           14:32:02 · ✓ done  │                                │
│  ▌  параллельно стримился рядом с Claude,       │                                │
│  ▌  отдельной панелью ниже.                     │                                │
│                                                  │                                │
│  ▌ ●  GEMINI 2.5 PRO          14:32:03 · ⏳ 187t │                                │
│  ▌  третья панель, всё ещё стримит…             │                                │
│                                                  │                                │
│  ─── router · aggregator picked GPT-5.5 ───      │                                │
├──────────────────────────────────────────────────┴────────────────────────────────┤
│ > █                                ⌘C cancel · Tab fold · ↑↓ scroll · / commands │
└───────────────────────────────────────────────────────────────────────────────────┘
```

Реализация:

```python
layout = Layout(name="root")
layout.split_column(
    Layout(name="header", size=1),
    Layout(name="body"),
    Layout(name="input", size=1),
    Layout(name="footer", size=1),
)
layout["body"].split_row(
    Layout(name="feed", ratio=3),     # единый чат
    Layout(name="side", ratio=1),     # узкая правая колонка
)
layout["side"].split_column(
    Layout(name="activity", ratio=1),
    Layout(name="tools", ratio=1),
)
```

### 4.3. Параллельный стриминг в едином фиде

**Ключевая идея:** UI НЕ читает токены напрямую из провайдеров. Провайдеры публикуют `StreamEvent` в `EventBus`. `ChatFeed` маршрутизирует event в нужный `MessagePanel` по `ev.meta.span_id` (каждый span = один panel).

```python
class ChatFeed:
    """Вертикальный список MessagePanel. Растёт сверху вниз; держит scroll-state."""
    def __init__(self, theme: Theme) -> None:
        self._panels: list[MessagePanel] = []
        self._by_span: dict[UUID, MessagePanel] = {}
        self._scroll_offset: int = 0             # 0 = прижато к низу (autoscroll)
        self._theme = theme
        self._lock = asyncio.Lock()

    async def open_panel(self, meta: CallerMeta) -> MessagePanel:
        async with self._lock:
            panel = MessagePanel(meta=meta, theme=self._theme.for_model(meta.model))
            self._panels.append(panel)
            self._by_span[meta.span_id] = panel
            return panel

    async def on_event(self, ev: StreamEvent) -> None:
        panel = self._by_span.get(ev.meta.span_id)
        if panel is None:
            return
        async with self._lock:
            panel.feed(ev)

    def render(self, viewport_height: int) -> RenderableType:
        # Берём хвост panels, помещающийся в viewport, с учётом scroll_offset
        rendered = [p.render() for p in self._panels]
        return Group(*self._slice_for_viewport(rendered, viewport_height))


class MessagePanel:
    """Одна панель = одно сообщение от одной модели. Растёт по мере стрима."""
    def __init__(self, meta: CallerMeta, theme: ModelTheme) -> None:
        self.meta = meta
        self._theme = theme
        self._buffer: list[str] = []           # full content, без maxlen — финальный рендер нужен целиком
        self._tail_window: deque[str] = deque(maxlen=4096)   # для лёгкого live-рендера
        self._tokens_out = 0
        self._first_token_ms: int | None = None
        self._started_at = monotonic()
        self._final_usage: UsageMetrics | None = None
        self._collapsed = False

    def feed(self, ev: StreamEvent) -> None:
        if ev.kind == "delta" and ev.text_delta:
            self._buffer.append(ev.text_delta)
            self._tail_window.append(ev.text_delta)
            self._tokens_out += 1
            if self._first_token_ms is None:
                self._first_token_ms = int((monotonic() - self._started_at) * 1000)
        elif ev.kind == "stop":
            self._final_usage = ev.final_usage

    def render(self) -> Panel:
        is_done = self._final_usage is not None
        if is_done:
            # Финальный рендер — Markdown, кодовые блоки автоматически Syntax-подсвечиваются
            body: RenderableType = Markdown("".join(self._buffer), code_theme="monokai")
        else:
            # Live-рендер — лёгкий Text с soft-wrap, только хвост окна
            body = Text("".join(self._tail_window), overflow="fold", no_wrap=False)

        title = Text.assemble(
            (f"{self._theme.glyph}  ", self._theme.accent),
            (self.meta.model.display_name, "bold"),
        )
        ts = self.meta.initiated_at.astimezone().strftime("%H:%M:%S")
        status = (
            f"✓ done · in {self._final_usage.input_tokens} · out {self._final_usage.output_tokens} · "
            f"TTFB {self._first_token_ms}ms · ${self._final_usage.cost_usd:.4f}"
            if is_done else
            f"⏳ streaming · {self._tokens_out}t"
        )
        subtitle = Text(f"{ts} · {status}", style="dim")

        return Panel(
            body,
            title=title, title_align="left",
            subtitle=subtitle, subtitle_align="right",
            border_style=self._theme.border,
            box=box.HEAVY_EDGE,                  # толстый левый бордер = "вертикальная отметка спикера"
            padding=(0, 1),
        )
```

**Параллельный fan-out выглядит так:**
1. Mediator получает `PARALLEL_COMPARE` шаг → синхронно вызывает `chat_feed.open_panel(meta)` для каждой модели → в фиде мгновенно появляются N пустых панелей подряд со spinner-subtitle.
2. Запускает `asyncio.TaskGroup` с N задач, каждая стримит свою модель. События идут в EventBus, ChatFeed диспетчирует по `span_id`.
3. Пользователь видит, как N панелей растут одновременно — но не пересекаются: каждая занимает свой блок в вертикальном фиде.

**Anti-tearing:**
- Все мутации `ChatFeed._panels` / `MessagePanel._buffer` под `asyncio.Lock`.
- `Live(layout, screen=True, redirect_stdout=True, redirect_stderr=True, refresh_per_second=20)`.
- SIGWINCH → `LayoutManager.rebuild()` (дебаунс 80 ms).

**Scroll:**
- Автоскролл к низу пока `_scroll_offset == 0`.
- `↑/↓` инкрементирует offset → автоскролл выключается, в footer появляется `[N new ↓]`.
- `End` сбрасывает offset → автоскролл включается обратно.
- `PgUp/PgDn` — постранично.

**Fold/expand:**
- `Tab` циклически переключает фокусную панель.
- `Enter` сворачивает/разворачивает фокусную. В свёрнутом виде — только title + subtitle + 1 строка превью.

### 4.7. Identity-стиль моделей (theme.py)

Каждая модель имеет триаду «глиф · цвет бордера · цвет акцента» — это её визуальная подпись в фиде.

```python
class ModelTheme(BaseModel):
    model_config = ConfigDict(frozen=True)
    glyph: str                   # один символ Unicode
    border: str                  # hex, для box.HEAVY_EDGE левого бордера
    accent: str                  # hex, для title-текста

MODEL_THEMES: dict[ProviderName, ModelTheme] = {
    ProviderName.ANTHROPIC: ModelTheme(glyph="◆", border="#C97B5C", accent="#E5A98C"),
    ProviderName.OPENAI:    ModelTheme(glyph="▲", border="#10A37F", accent="#5BD3B0"),
    ProviderName.GOOGLE:    ModelTheme(glyph="●", border="#8AB4F8", accent="#C7D8FB"),
}

ROUTER_THEME = ModelTheme(glyph="✦", border="#A78BFA", accent="#C7B6FF")
SUBAGENT_THEMES: dict[AgentName, ModelTheme] = { ... }   # каждый sub-agent тоже имеет свою отметку
```

Правило: цвет бордера ВСЕГДА = цвет провайдера модели; цвет глифа в title = `accent` темы агента (router/architect/tester). Это позволяет одним взглядом понять: «◆ Claude отвечает от имени Tester» vs «▲ GPT отвечает от имени Architect».

### 4.4. Лог вызова плагинов/скиллов

Используется `rich.tree.Tree`, обновляемый инкрементально:

```
router
├─ search_symbols(query="UserAuth")          ✓ 3 matches · 12ms
├─ get_impact_radius(symbol="auth.login")    ✓ risk=0.42 · 27ms
└─ dispatch → architect
   ├─ read_file("app/auth/login.py", 1, 80)  ✓ 1.2 KB
   └─ propose_refactor()                     ▰▱ streaming…
```

Каждая нода — узел `Tree`. Статус-иконы:
- `▰▱` — в процессе (cyclic spinner-glyph, перерисовывается)
- `✓` зелёный — успех
- `✗` красный — ошибка с разворачиваемой стектрейс-нодой

### 4.5. Спиннеры и микро-анимации

Регистрация кастомных:

```python
CUSTOM_SPINNERS = {
    "ivy-pulse":  {"interval": 90,  "frames": ["▰▱▱▱", "▱▰▱▱", "▱▱▰▱", "▱▱▱▰", "▱▱▰▱", "▱▰▱▱"]},
    "ivy-orbit":  {"interval": 110, "frames": ["◜","◠","◝","◞","◡","◟"]},
    "ivy-stream": {"interval": 60,  "frames": ["▏","▎","▍","▌","▋","▊","▉","▊","▋","▌","▍","▎"]},
}
# rich.spinner.SPINNERS.update(CUSTOM_SPINNERS)
```

Использование:
- Router планирует → `ivy-pulse` в activity-панели.
- LLM стримит → `ivy-stream` в подзаголовке model-panel.
- Skill выполняется → `ivy-orbit` в tool-tree.

### 4.6. Статус-бар (footer)

Однострочный `rich.text.Text` с разделителями `·`. Обновляется на каждый `StreamEvent` или `AgentEvent`. Слева — управляющие подсказки, справа — суммарные usage-метрики сессии.

---

## 5. Системный промпт Router-а (эталон)

Файл: `ivycode/agents/prompts/router.md`. Загружается через `pathlib`, вставляется первой message с `role=system`.

```markdown
# ROLE
You are **Router**, the planning brain of *ivycode*. You do NOT write code, you do NOT read files directly, and you do NOT call external LLMs yourself. Your single output is a JSON object that strictly matches the `ExecutionPlan` schema provided below.

# OPERATING CONTEXT
You are given:
1. The user's task in natural language.
2. A `GraphSnapshot` produced by the local CodeGraph (symbols, routes, file boundaries — NOT raw source).
3. A registry of available sub-agents and skills with their JSON schemas.
4. The strict `ExecutionPlan` JSON schema you MUST emit.

# HARD RULES
1. **CodeGraph-first.** Before delegating ANY coding task, you MUST include at least one `graph_query` step that calls `search_symbols` or `get_impact_radius` to ground the plan in real symbols. If the user's request mentions a name, route, or behavior, that grounding is mandatory.
2. **No raw file reads in the plan.** Sub-agents access source code only through `read_file` with explicit `(file_path, line_start, line_end)` ranges derived from `SymbolBrief` objects you provide in `inputs`.
3. **Token discipline.** For each `SubAgentDirective` you MUST set `token_budget`. Sum of budgets must not exceed `estimated_total_tokens`.
4. **Schema enforcement.** Whenever a sub-agent must return structured data, you MUST attach a JSON Schema in `expected_output_schema`. Free-form text is allowed ONLY for the final user-facing answer.
5. **Parallelism.** Use `parallel_compare` only when the task explicitly benefits from cross-model comparison (architecture decisions, ambiguous design). Never use it for deterministic operations (refactor, test generation).
6. **Dependency hygiene.** A step may reference outputs of earlier steps ONLY via `depends_on`. Cyclic or forward references are forbidden.
7. **Risk assessment.** Set `risk_level` to `high` whenever the plan modifies files referenced by `ImpactReport.transitive_callers_count > 10` or touches authentication/payment/persistence layers.
8. **Output format.** Respond with a SINGLE JSON object. No prose, no Markdown fences, no commentary. The JSON MUST validate against the `ExecutionPlan` schema below.

# VALIDATION CONTRACT
You will be called again with `validation_error` if your output fails Pydantic validation. On retry, fix ONLY the reported issues and re-emit the full plan. You have at most 2 retries.

# SUB-AGENT VALIDATION PROTOCOL
For each `SubAgentDirective` you emit:
- The `instructions` field MUST end with the literal sentence:
  > "Return ONLY a JSON object matching the provided schema. Any deviation will be rejected."
- The `expected_output_schema` MUST be a valid JSON Schema draft-2020-12 fragment.
- The aggregator step (if present) MUST validate every sub-agent output against its declared schema before merging.

# ANTI-PATTERNS (you will be penalized for these)
- Emitting a `subagent` step without a prior `graph_query` step that grounds it.
- Passing `inputs` containing entire file contents instead of symbol references.
- Using `parallel_compare` for tasks with a single deterministic answer.
- Producing prose or Markdown around the JSON object.
- Setting `token_budget` higher than 16000 for any single sub-agent step.

# JSON SCHEMA (authoritative)
<<<schema:ExecutionPlan>>>

# USER TASK
<<<user_task>>>

# GRAPH SNAPSHOT
<<<graph_snapshot_json>>>

# AVAILABLE SUB-AGENTS
<<<subagents_registry_json>>>

# AVAILABLE SKILLS
<<<skills_registry_json>>>
```

**Механика подстановки плейсхолдеров** (в `RouterAgent._render_system_prompt`):

```python
def _render_system_prompt(self, ctx: RouterContext) -> str:
    template = self._prompt_template
    return (
        template
        .replace("<<<schema:ExecutionPlan>>>", json.dumps(ExecutionPlan.model_json_schema(), indent=2))
        .replace("<<<user_task>>>", ctx.user_task)
        .replace("<<<graph_snapshot_json>>>", ctx.snapshot.model_dump_json(indent=2))
        .replace("<<<subagents_registry_json>>>", self._mediator.describe_subagents_json())
        .replace("<<<skills_registry_json>>>", self._skills.describe_json())
    )
```

**Валидация и retry:**

```python
async def plan(self, ctx: RouterContext) -> ExecutionPlan:
    for attempt in range(3):
        raw = await self._provider.complete_json(
            system=self._render_system_prompt(ctx),
            user="Produce the ExecutionPlan now.",
            response_schema=ExecutionPlan.model_json_schema(),
        )
        try:
            return ExecutionPlan.model_validate_json(raw, strict=True)
        except ValidationError as e:
            if attempt == 2:
                raise RouterPlanInvalidError(errors=e.errors(), raw_output=raw)
            ctx = ctx.with_validation_error(e)   # подмешивает в следующий промпт
    raise AssertionError("unreachable")
```

---

## 6. Спецификация провайдеров

### 6.1. ABC

```python
class LLMProvider(ABC):
    name: ClassVar[ProviderName]

    @abstractmethod
    async def stream(
        self,
        *,
        system: str,
        messages: Sequence[Message],
        tools: Sequence[ToolSchema] = (),
        response_schema: dict[str, object] | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.2,
        meta: CallerMeta,
    ) -> AsyncIterator[StreamEvent]: ...

    @abstractmethod
    async def complete_json(
        self,
        *,
        system: str,
        user: str,
        response_schema: dict[str, object],
        meta: CallerMeta,
    ) -> str: ...

    @abstractmethod
    def estimate_tokens(self, text: str) -> int: ...
```

### 6.2. Особенности адаптеров

| Провайдер | Стрим | Структурный выход | Tool use | Кеширование |
|---|---|---|---|---|
| **Anthropic** | SSE `messages.stream` | Через `tool_use` с фиктивным «return_plan» tool, форсируется через `tool_choice` | Native | `cache_control: ephemeral` для system prompt |
| **OpenAI** | SSE `responses.stream` | Native `response_format={"type":"json_schema", ...}` | Native | через `prompt_cache_key` |
| **Google** | gRPC stream | `response_mime_type="application/json"` + `response_schema` | Native | через `cached_content` (контент-кеш) |

Каждый адаптер обязан конвертировать вендорские стрим-события в унифицированные `StreamEvent`.

---

## 7. Mediator и SubAgent

### 7.1. Mediator

```python
class AgentMediator:
    def __init__(self, runtime: Runtime) -> None:
        self._runtime = runtime
        self._subagents: dict[AgentName, SubAgent] = {}

    def register(self, agent: SubAgent) -> None: ...

    async def dispatch(self, plan: ExecutionPlan) -> list[StepResult]:
        results: dict[str, StepResult] = {}
        for step in self._topo_sort(plan.steps):
            await self._await_dependencies(step, results)
            match step.kind:
                case StepKind.GRAPH_QUERY:
                    results[step.id] = await self._run_graph_query(step)
                case StepKind.SUBAGENT:
                    results[step.id] = await self._run_subagent(step, results)
                case StepKind.PARALLEL_COMPARE:
                    results[step.id] = await self._run_parallel(step, results)
                case StepKind.AGGREGATE:
                    results[step.id] = await self._run_aggregate(step, results)
        return list(results.values())
```

### 7.2. SubAgent base

```python
class SubAgent(ABC):
    name: ClassVar[AgentName]
    default_model: ClassVar[ModelRef]
    system_prompt_path: ClassVar[Path]

    async def execute(self, directive: SubAgentDirective, ctx: AgentContext) -> StepResult:
        provider = ctx.runtime.providers.get(self.default_model)
        messages = self._build_messages(directive, ctx)
        meta = CallerMeta(agent=self.name, model=self.default_model, parent_span_id=ctx.parent_span)
        raw = await provider.complete_json(
            system=self._render_system_prompt(directive),
            user=directive.instructions,
            response_schema=directive.expected_output_schema or {"type": "object"},
            meta=meta,
        )
        output = self._validate(raw, directive.expected_output_schema)
        return StepResult(step_id=ctx.step_id, success=True, output=output, ...)
```

---

## 8. Skills

### 8.1. Декоратор

```python
@skill(
    name="search_symbols",
    description="Search code symbols by name using local CodeGraph FTS5 index.",
    permissions=["graph:read"],
)
async def search_symbols(query: str, limit: int = 20) -> list[SymbolBrief]:
    return await runtime.codegraph.search_symbols(query, limit=limit)
```

Декоратор:
1. Извлекает сигнатуру через `inspect.signature` + аннотации.
2. Генерирует JSON Schema через `pydantic.TypeAdapter(...).json_schema()`.
3. Регистрирует в `SkillRegistry`.
4. Оборачивает в async-метрикатор (latency, success/failure).

### 8.2. Контракт безопасности

- `write_file` запрещён, если путь вне `project_root`.
- `run_command` идёт через `asyncio.create_subprocess_exec` с whitelist бинарей из `config.toml`.
- `web.fetch` уважает `robots.txt` и таймаут 10 s.

---

## 9. Settings (pydantic-settings)

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="IVYCODE_",
        env_file=".env",
        toml_file=Path.home() / ".ivycode" / "config.toml",
    )
    anthropic_api_key: SecretStr
    openai_api_key: SecretStr
    google_api_key: SecretStr
    default_router_model: ModelRef = ModelRef(
        provider=ProviderName.ANTHROPIC,
        model_id="claude-opus-4-7",
        display_name="Claude Opus 4.7",
    )
    active_panel_providers: list[ModelRef]
    project_root: Path = Field(default_factory=Path.cwd)
    cache_dir: Path = Path.home() / ".ivycode" / "cache"
    history_dir: Path = Path.home() / ".ivycode" / "history"
    max_concurrent_providers: PositiveInt = 4
    request_timeout_s: PositiveInt = 120
```

---

## 10. CLI

```python
# ivycode/cli/app.py
app = typer.Typer(rich_markup_mode="rich", no_args_is_help=True)

@app.command()
def chat(model: list[str] = typer.Option(None, "--model", "-m")) -> None:
    """Open interactive multi-model chat session."""
    asyncio.run(Runtime.bootstrap_and_run_chat(models=model))

@app.command()
def plan(task: str) -> None:
    """Produce an ExecutionPlan for the given task without executing it."""
    asyncio.run(Runtime.bootstrap_and_plan(task))

@app.command()
def index(force: bool = False) -> None:
    """Re-index the current project into CodeGraph."""
    asyncio.run(Runtime.bootstrap_and_index(force=force))

@app.command()
def doctor() -> None:
    """Diagnose configuration, API keys, graph health."""
    asyncio.run(Runtime.run_doctor())
```

---

## 11. Persistence

- **History:** `~/.ivycode/history/{YYYY-MM-DD}/{session_id}.jsonl`. Каждая строка — `Message.model_dump_json()`. Дополнительно `transcript.json` с `SessionTranscript`.
- **Cache:** `diskcache.Cache(settings.cache_dir / "llm")`. Ключ: `sha256(provider + model_id + system + messages_json + tools_hash + response_schema_hash)`. TTL: 24 h для неструктурного, 7 дней для структурного.

---

## 12. Тестирование

- **unit:** Pydantic-схемы (round-trip), Router validators (генерация невалидных JSON, проверка retry), CodeGraph projection.
- **integration:** Запись/воспроизведение сессий через `vcrpy` для каждого провайдера. Тест параллельного стрима с фейковыми SSE-источниками.
- **smoke:** `ivycode doctor` зелёный на CI; `ivycode index` индексирует фикстурный репо за < 5 s.

Целевое покрытие: ≥ 85% строк, 100% для `core/envelope.py`, `agents/validators.py`, `codegraph/projection.py`.

---

## 13. Что считать «готовым» (Definition of Done)

1. `python -m ivycode chat -m anthropic/claude-opus-4-7 -m openai/gpt-5.5-xhigh -m google/gemini-2.5-pro` запускается, показывает 3 параллельных стрим-панели на любом тестовом запросе.
2. `ivycode plan "Refactor login flow to use OAuth"` печатает валидный `ExecutionPlan`, содержащий минимум один `graph_query` шаг.
3. `ivycode index` строит граф для самого репозитория `ivycode/` без ошибок.
4. `mypy --strict ivycode/` — 0 ошибок.
5. `ruff check .` — 0 ошибок.
6. `pytest -q` — все тесты зелёные.
7. UI корректно перерисовывается при ресайзе терминала вплоть до 80×24.
8. На отключённой сети `ivycode doctor` чётко рапортует, какие провайдеры недоступны, без падений.

---

## 14. Что НЕ делать (явный negative scope)

- Не использовать LangChain / LlamaIndex / CrewAI / AutoGen — оркестрация пишется с нуля.
- Не вводить плагинную систему на entry_points — динамическая загрузка только из `~/.ivycode/plugins/`.
- Не сохранять API-ключи нигде, кроме `SecretStr` в `Settings` и keyring.
- Не использовать `asyncio.create_task` без trackback в общий `TaskGroup` — никаких «сирот».
- Не писать собственный SSE-парсер — использовать встроенные стрим-методы SDK провайдеров.

---

## 15. Порядок реализации (для исполнителя)

1. `pyproject.toml` + `ivycode/__init__.py` + `core/settings.py` + `core/envelope.py`.
2. `ui/theme.py` + `ui/console.py` + `ui/layout.py` + базовый `ModelPanel`.
3. `providers/base.py` + один реальный адаптер (`anthropic_provider.py`), второй (`openai`), третий (`google`).
4. `codegraph/service.py` + `snapshot.py` + `projection.py` (интеграция библиотеки CodeGraph).
5. `skills/` (registry + builtins/graph.py + builtins/fs.py).
6. `agents/base.py` + `agents/router.py` + `agents/mediator.py` + один SubAgent (`architect`).
7. `orchestration/parallel.py` + `ui/live_session.py` + связка через `EventBus`.
8. `cli/app.py` + `cli/commands/*` + REPL.
9. Остальные SubAgents (`refactorer`, `tester`, `documenter`).
10. Тесты, `doctor`, persistence, polish.

**Каждый коммит — атомарный, тесты зелёные, mypy чистый.**

---

## 16. Управление контекстом длинной сессии (ContextWindow)

`SessionTranscript` хранит ВСЁ для persistence. Но в LLM нельзя отправлять всё — нужен отдельный слой, который собирает компактный prompt из истории под каждый вызов.

### 16.1. Модель

```python
class ContextStrategy(StrEnum):
    SLIDING = "sliding"              # просто tail последних N токенов
    SUMMARIZED = "summarized"        # старое → summary блоки
    HIERARCHICAL = "hierarchical"    # default: pinned + recent + summaries

class SummaryBlock(BaseModel):
    model_config = ConfigDict(frozen=True)
    covers_message_ids: list[UUID]
    summary_text: str
    token_count: PositiveInt
    created_at: datetime
    summarizer_model: ModelRef

class ContextWindow(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)   # для deque
    pinned: list[Message] = Field(default_factory=list)
    recent: deque[Message] = Field(default_factory=lambda: deque())
    summaries: list[SummaryBlock] = Field(default_factory=list)
    target_tokens: PositiveInt                # 70% от context window модели
    hard_ceiling_tokens: PositiveInt          # 90% от context window
    strategy: ContextStrategy = ContextStrategy.HIERARCHICAL
```

### 16.2. Что попадает в `pinned` (никогда не выпадает)

1. Системный промпт текущего агента.
2. Последний `user` message (исходная задача текущего раунда).
3. Последний `ExecutionPlan` Router-а, обёрнутый как `<plan>...</plan>` в одно сообщение.
4. Активные «закрепы» (`/pin <message_id>` от пользователя).

### 16.3. Алгоритм сжатия (hierarchical)

Псевдокод, выполняется ПЕРЕД каждым вызовом провайдера:

```python
async def materialize(self, window: ContextWindow, provider: LLMProvider) -> list[Message]:
    total = self._count(window.pinned + list(window.recent), provider)
    total += sum(s.token_count for s in window.summaries)

    # Шаг 1: пока > target — вырезаем старейший recent → ставим в очередь на summary
    pending_for_summary: list[Message] = []
    while total > window.target_tokens and len(window.recent) > 4:
        victim = window.recent.popleft()
        pending_for_summary.append(victim)
        total -= self._count([victim], provider)

    # Шаг 2: батч-summarize очереди дешёвой быстрой моделью
    if pending_for_summary:
        block = await self._summarize_batch(pending_for_summary, provider_for_summary=self._fast_model)
        window.summaries.append(block)
        total += block.token_count

    # Шаг 3: если всё ещё > hard_ceiling — recursive merge двух старейших summaries
    while total > window.hard_ceiling_tokens and len(window.summaries) >= 2:
        merged = await self._merge_summaries(window.summaries[0], window.summaries[1])
        total -= window.summaries[0].token_count + window.summaries[1].token_count
        window.summaries = [merged] + window.summaries[2:]
        total += merged.token_count

    # Шаг 4: если всё ещё не помещается — ContextOverflowError, пусть CLI спросит юзера
    if total > window.hard_ceiling_tokens:
        raise ContextOverflowError(total=total, ceiling=window.hard_ceiling_tokens)

    return self._assemble(window)
```

### 16.4. Промпт суммаризатора (дешёвая модель: Haiku / Gemini Flash)

```markdown
# ROLE
You compress a slice of a developer/assistant conversation into a structured digest.

# HARD CONSTRAINTS
- Output ≤ 400 tokens.
- Preserve, in priority order:
  1. Decisions made (architectural, naming, library choices).
  2. Files touched, with line ranges as `path:start-end`.
  3. Errors encountered + how they were resolved.
  4. Tool calls in shorthand: `tool(args_brief)→outcome`.
- Drop: pleasantries, repeated context, verbose code blocks.
- Replace any code block longer than 10 lines with a reference: `[code: file.py:12-45]` — it is recoverable via CodeGraph.
- Output format: Markdown with sections `## Decisions`, `## Files`, `## Errors`, `## Tools`. No prose intro.

# SLICE
<<<messages_json>>>
```

### 16.5. CodeGraph-дедупликация

Перед материализацией `recent` проходим оптимизатором:
- Для каждого `tool_result` от `read_file(path, start, end)` оставляем ТОЛЬКО последний для данной тройки `(path, start, end)`. Все более ранние заменяются на placeholder-message: `[tool_result for read_file(...) superseded by message <id>]`.
- Аналогично для `search_symbols` с одинаковым query — оставляем последний.
- Это типично экономит 15–25% recent-окна на длинных сессиях, где модель повторно запрашивает одни и те же файлы.

### 16.6. Per-agent окна

`ContextWindow` — не одно на сессию. Mediator конструирует **отдельное окно под каждый вызов SubAgent-а**:

| Агент | Что в pinned | Что в recent |
|---|---|---|
| Router | system + последний user task | последние 3 шага из StepResults |
| Architect | system + текущий SubAgentDirective | релевантные SymbolBrief из inputs |
| Tester | system + директива + результат предшествующего graph_query | пусто |
| Documenter | system + директива | последний финальный ответ агрегатора |

Это даёт двойную экономию: SubAgent не видит чужую переписку, и его окно почти всегда влезает без summary.

### 16.7. Лимиты по моделям

```python
MODEL_CONTEXT_LIMITS: dict[str, int] = {
    "claude-opus-4-7":   200_000,
    "gpt-5.5-xhigh":     400_000,
    "gemini-2.5-pro":  1_000_000,
}

def compute_targets(model_id: str) -> tuple[int, int]:
    limit = MODEL_CONTEXT_LIMITS[model_id]
    return int(limit * 0.70), int(limit * 0.90)   # target, hard_ceiling
```

### 16.8. CLI-команды управления

| Команда | Поведение |
|---|---|
| `/compact` | Принудительно сжимает все `recent` старше 5 минут в один summary (≤ 200 токенов). |
| `/fresh` | Создаёт новую сессию, переносит только `pinned`. |
| `/pin <id>` | Закрепляет message по id, чтобы он никогда не выпадал. |
| `/unpin <id>` | Снимает закреп. |
| `/context` | Показывает текущее распределение токенов: pinned / recent / summaries / free. |

### 16.9. UI-индикатор

В footer постоянно отображается `ctx 42% (84k/200k)`. Цвет:
- < 60% — dim white,
- 60–80% — `#A78BFA`,
- 80–90% — `#E5A98C` (внимание),
- > 90% — `#FF6B6B` blink (вот-вот overflow).

При срабатывании автоматического сжатия в `activity`-панель прилетает событие: `✦ context compressed: 4 messages → 1 summary (saved 3,840 tok)`.

---

## 17. Design System (зафиксированные решения)

Все значения ниже — **финальные**. Используются как единственный источник истины для `ui/theme.py`, `ui/console.py`, `ui/panels/*`. Любое отклонение требует апдейта этого раздела.

### 17.1. Mood: Quiet Luxury Terminal

| Токен | Hex | Назначение |
|---|---|---|
| `bg.base` | `#0B0D12` | Основной фон |
| `bg.elevated` | `#11141B` | Hover/focus, выделенные блоки |
| `text.primary` | `#E6E6E6` | Основной текст |
| `text.dim` | `#6B7280` | Subtitle, timestamp, hints |
| `text.muted` | `#3A3F4A` | Borders, dividers |
| `accent.warm` | `#E5A98C` | Главный акцент (бордеры активных, hover) |
| `accent.mint` | `#7CFFB2` | Success, complete |
| `accent.violet` | `#A78BFA` | Router/system events |
| `accent.cyan` | `#8AB4F8` | Info, links |
| `warn` | `#FFB070` | Внимание (slow response, deprecated) |
| `error` | `#FF6B6B` | Ошибки, failures |
| `model.anthropic` | `#C97B5C` | Левый бар Claude |
| `model.openai` | `#10A37F` | Левый бар GPT |
| `model.google` | `#8AB4F8` | Левый бар Gemini |
| `model.local` | `#94A3B8` | Локальные модели (Ollama, vLLM) |

### 17.2. Density: Roomy

- `panel.padding = (1, 2)` — одна строка сверху/снизу, два пробела слева/справа.
- `feed.message_gap = 1` — одна пустая строка между сообщениями.
- `feed.section_gap = 2` — две строки между крупными секциями (welcome → first message).
- `subtitle_gap = 1` — одна пустая строка между телом сообщения и subtitle-метрикой.

### 17.3. Motion: Living

- **Спиннеры:** кастомные `ivy-pulse`, `ivy-orbit`, `ivy-stream` (см. §4.5).
- **Cursor:** мерцает с интервалом 600 ms (`prompt_toolkit` `Cursor.blink_rate`).
- **Active panel pulse:** левый бар активного `MessagePanel` плавно меняет яркость bg-фона строки на ±5% c периодом 1.4 s (через `rich.live` redraw).
- **Token counter:** в subtitle стрим-панели цифра `out 187t` инкрементально tick-ает по мере стрима (не «прыгает» сразу на 1000, а проходит через промежуточные значения визуально через debounce 80 ms).
- **Progress bars** для reindex / index: rich Progress с bar_width пропорциональным ширине side-панели.
- **A11y override:** `IVYCODE_MOTION=static` отключает все анимации (для SSH, CI, screen readers).

### 17.4. Input: slash + @ + # + ! + Ctrl+P

| Префикс | Назначение | Триггер автокомплита |
|---|---|---|
| `/` | Слэш-команды: `/compact`, `/pin`, `/fresh`, `/model`, `/plugins`, `/context`, `/understand` | Из `SkillRegistry` + статических команд |
| `@` | Пути к файлам с glob: `@src/auth/login.py`, `@src/**/*.ts` | `pathlib.Path.glob` от `project_root` |
| `#` | Символы из CodeGraph: `#authenticate_user` | `CodeGraphService.search_symbols(prefix, limit=8)` |
| `!` | Shell-команда in-place: `!pytest tests/auth/` | История `shell` history-файла |
| `Ctrl+P` | Command Palette (fuzzy по всем командам) | Все источники объединены, ранжированы по recency |
| `↑/↓` | История запросов сессии | `~/.ivycode/history/{session}/input.jsonl` |
| `Tab` | Циклически переключает фокусную панель | — |
| `Enter` (на свёрнутой панели/tool-карточке) | Развернуть/свернуть | — |

**Реализация:** `prompt_toolkit.PromptSession` с кастомным `Completer`, который маршрутизирует по первому символу токена под курсором. `mention-style` подсветка для `@`, `#`, `!` (другой цвет).

### 17.5. Bubble: Left-bar marker

```
▏ ◆  claude opus 4.7         14:32 · ✓ done
▏
▏  тело сообщения, полная ширина фида
▏  (минус правая sidebar и padding)
▏
▏    · markdown lists поддерживаются
▏    · код подсвечивается через Syntax
▏
▏  in 1,204 → out 318 · $0.0042 · TTFB 412ms
```

Реализация: НЕ `Panel`, а кастомный `Group(prefix_column, content_column)`. `prefix_column` — это `Text("▏\n" * lines, style=model_theme.border)` с одинаковой высотой, что у content. Это даёт сплошную вертикальную полосу без верхней/нижней рамки.

Title строка отделяется одной пустой строкой от тела (см. §17.2). Subtitle (с usage-метриками) тоже отделена пустой строкой.

### 17.6. Tool calls: короткие глагольные ярлыки + collapsible

Имена в title — **строго глаголы**: `Search`, `Read`, `Run`, `Write`, `Update`, `Plan`, `Index`, `Explain`, `Diff`, `Dashboard`. Полное имя skill-а (`search_symbols`, `read_file`) — внутри развёрнутой карточки.

Маппинг skill-имени → display-verb регистрируется в `SkillRegistry`:

```python
@skill(
    name="search_symbols",
    display_verb="Search",
    description="Search code symbols by name using local CodeGraph FTS5 index.",
)
async def search_symbols(query: str, limit: int = 20) -> list[SymbolBrief]: ...
```

Карточка в фиде (свёрнута по умолчанию):

```
▏ ✦  router                  14:32:01
▏
▏  ┌─ ▸ Search · 12ms ────────────────────────┐
▏  │ "UserAuth" → 3 matches                   │
▏  └──────────────────────────────────────────┘
▏  ┌─ ▸ Impact · 27ms ────────────────────────┐
▏  │ "auth.login.authenticate" → risk 0.42    │
▏  └──────────────────────────────────────────┘
```

Развёрнута (по Enter):

```
▏  ┌─ ▾ Impact · 27ms ────────────────────────┐
▏  │ skill: get_impact_radius                 │
▏  │ symbol: "auth.login.authenticate"        │
▏  │ ──────────────────────────────────────── │
▏  │ result:                                  │
▏  │   risk_score: 0.42                       │
▏  │   direct_callers (4):                    │
▏  │     · routes.api.login                   │
▏  │     · routes.api.oauth_callback          │
▏  │     · cli.commands.relogin               │
▏  │     · tests.auth.test_login              │
▏  │   transitive_callers_count: 17           │
▏  │   affected_files: 6                      │
▏  └──────────────────────────────────────────┘
```

Иконография: `▸` свёрнуто, `▾` развёрнуто, `✗` ошибка (бордер красный).

Полный список глаголов:

| Skill | Verb |
|---|---|
| `search_symbols` | `Search` |
| `get_impact_radius` | `Impact` |
| `get_framework_routes` | `Routes` |
| `read_file` | `Read` |
| `write_file` | `Write` |
| `apply_patch` | `Update` |
| `run_command` | `Run` |
| `web_fetch` | `Fetch` |
| `web_search` | `Web` |
| `reindex_path` | `Index` |
| `dispatch` (mediator) | `Plan` |
| `understand_explain` | `Explain` |
| `understand_diff` | `Diff` |
| `open_dashboard` | `Dashboard` |

### 17.7. Status bar (footer) — все 4 индикатора

Однострочный, разделители — `·`. Слева направо:

```
◆ claude / architect   ·   graph 1247 sym · fresh   ·   ctx ████████░░░░ 42%   ·   ⌘P palette · ⌘C cancel
```

**Сегменты:**
1. **Active model + agent.** Глиф модели (с цветом её темы) + display_name модели + `/` + имя текущего агента. Обновляется на каждый `agent_dispatch` событие.
2. **CodeGraph status.** `graph {N} sym · {fresh|stale|indexing M/K}`. Цвет: `fresh` mint, `stale` warm, `indexing` violet с pulse.
3. **Context bar.** Прогресс-бар (12 cells) + проценты. Цвета: <60% dim, 60–80% violet, 80–90% warm, >90% error+blink. На hover (фокус через `Tab` в footer-mode) показывает breakdown `pinned 2k · recent 18k · sum 4k`.
4. **Hotkey hints.** Контекстные подсказки 2-3 ключевых клавиш. Меняются по фокусу: в чате `⌘P · ⌘C · /`, в фокусе панели — `Enter fold · /pin · /copy`.

**Toasts** появляются на 2 секунды поверх правой части footer-а (вытесняя hotkey hints):

```
◆ claude / architect   ·   graph 1247 sym · fresh   ·   ctx 42%   ·   ✓ pinned msg #a3f2
```

### 17.8. Voice: Precision

Все системные сообщения — **сухие, инженерные, факты+числа**. Никаких «Plan is ready, shall I proceed?». Шаблон: `<short verb> · <metric/result>`.

Каноничный лексикон:

| Событие | Текст |
|---|---|
| Router закончил план | `plan ready · 4 steps · risk=low · est 3.2k tok` |
| CodeGraph reindex старт | `reindex start · 40 files queued` |
| CodeGraph reindex прогресс | `reindex 23/40 · 1.4s elapsed` |
| CodeGraph reindex финиш | `reindex done · 40 files · +12 symbols · 2.1s` |
| Context compaction | `ctx compacted · 4 msg → 1 summary · saved 3,840 tok` |
| Pin сообщения | `pinned · msg #a3f2 · ctx +0 tok` |
| Model switch | `model · claude-opus-4-7 → gpt-5.5-xhigh` |
| Provider unavailable | `provider · anthropic 429 · retry in 12s` |
| Subagent dispatch | `dispatch · architect · budget 6k tok` |
| Plugin loaded | `plugin · understand-anything · ready` |

Глифы префиксов: `✨ router · ✮ graph · ◈ ctx · ◆▲● model · ⚠ error · ✓ done`.

### 17.9. Errors: Inline diagnostic card

Каждая ошибка — отдельная карточка в фиде. Левый бар — `error` цвет. Title — `⚠ error · <provider/component> · <error_code>`. Внутри: одно предложение причины, конкретное действие. Затем — карточка `next steps` с однобуквенными хоткеями.

Pydantic-модель события:

```python
class ErrorEvent(BaseModel):
    model_config = ConfigDict(frozen=True)
    component: Literal["provider", "codegraph", "skill", "agent", "validator", "transport"]
    code: str                        # "rate_limit", "context_overflow", "schema_invalid", "timeout"
    summary: Annotated[str, Field(min_length=10, max_length=200)]
    cause: Annotated[str, Field(max_length=400)] | None = None
    recovery_actions: list[RecoveryAction] = Field(min_length=1)
    stacktrace: str | None = None    # скрыта под [T] toggle
    meta: CallerMeta

class RecoveryAction(BaseModel):
    model_config = ConfigDict(frozen=True)
    hotkey: Annotated[str, Field(min_length=1, max_length=2)]
    label: Annotated[str, Field(min_length=3, max_length=60)]
    command: str                     # внутренний command-id, не shell
```

Карточка рендерится:

```
▏ ⚠  error · provider · rate_limit              14:32
▏
▏  anthropic temporarily unavailable (429)
▏  retry in 12s
▏
▏  ┌─ next steps ──────────────────────────────┐
▏  │  [R] retry now                            │
▏  │  [S] switch to gpt-5.5                    │
▏  │  [W] wait 12s & retry                     │
▏  │  [T] toggle stacktrace                    │
▏  └───────────────────────────────────────────┘
```

Хоткеи активны пока карточка в viewport. После выбора — карточка получает дополнительную строку `→ chose: retry now` и блокируется.

### 17.10. Code rendering: Syntax + line numbers + язык-бейдж

Внутри `MessagePanel` Markdown-рендер заменяет fenced code blocks на `rich.syntax.Syntax`:

```python
SYNTAX_THEME = "monokai"     # тёмная база, мягкие тона согласуется с palette
SYNTAX_OPTS = dict(
    theme=SYNTAX_THEME,
    line_numbers=True,
    indent_guides=True,
    word_wrap=False,           # горизонтальный scroll вместо переноса
    background_color="#0B0D12",
)
```

Каждый код-блок обёрнут в мини-`Panel` с title = язык, subtitle = `[c] copy · [s] save · [r] run`:

```
┌─ python ──────────────────────────────────────────── [c] [s] [r] ─┐
│  1  async def authenticate(req: Request) -> User:                 │
│  2      token = req.headers.get("authorization")                  │
│  3      if not token:                                             │
│  4          raise HTTPException(401, "missing token")             │
│  5      return await session.get_user(token)                      │
└───────────────────────────────────────────────────────────────────┘
```

- `[c]` — копирует код в системный clipboard (`pyperclip` с fallback на OSC 52 escape для SSH).
- `[s]` — сохраняет в `~/.ivycode/snippets/{session}/{seq}.{ext}`.
- `[r]` — выполняет (только для shell блоков, после явного подтверждения).

Diff-блоки (язык `diff` или `patch`): `Syntax` автоматически подсвечивает `+`/`-` строки. Дополнительно — green/red bg для линий.

### 17.11. Welcome screen

При запуске `ivycode chat` (без аргументов) показывается на 1 экран:

```


     ❖  ι v y c o d e
     ────────────────────────────────────
     multi-agent CLI · v0.1.0

     project   ~/code/myapp on feat/oauth
     graph     1,247 symbols · fresh
     models    ◆ claude  ▲ gpt  ● gemini

     ▏ try
     ▏   · ask anything in plain language
     ▏   · / for commands  · @ for files
     ▏   · # for symbols   · ! for shell
     ▏   · ⌘P for command palette

     ready when you are →


```

**Композиция:**
- Лого `❖  ι v y c o d e` — `Text` с разрядкой между буквами, `style="bold #E5A98C"`, глиф `❖` — `accent.warm`.
- Дивайдер — `─` × ширина_лого.
- `multi-agent CLI · v{version}` — `dim`.
- Блок status: 3 строки в формате `{label:9}{value}`, label dim, value primary.
  - `project` берётся из `git rev-parse --show-toplevel` и `git branch --show-current`. Если не git-репо — `(no git)`.
  - `graph` — из `CodeGraphService.stats()`.
  - `models` — иконки моделей, заявленных в `--model` или дефолтных.
- Блок `try` — `left-bar marker` стиль с накопленными hint-ами. **Адаптивный:** убирает пункты, которые не сконфигурированы (например, `⌘P` не показывается, если терминал не поддерживает `application keypad`).
- `ready when you are →` — `dim italic`, последняя строка.

На повторном запуске (`ivycode chat` в проекте с историей) Welcome редуцируется до 3 строк:

```
ivycode · ~/code/myapp on feat/oauth · ctx 0% · graph fresh
last session 2 hours ago · /resume to continue
ready when you are →
```

---

## 18. Транспортный слой: WireCodec + ProviderProfile + custom base URLs

Бизнес-агенты (Router, SubAgents) НЕ знают, идёт ли запрос в облако вендора, в Ollama на `localhost:11434` или в self-hosted vLLM на корпоративном GPU-сервере. Это даёт три эффекта: (а) поддержка локальных моделей без касания агентов, (б) лёгкий swap провайдеров при rate-limit, (в) тестируемость через локальный mock-сервер.

### 18.1. Слои

```
Router/SubAgent
   ↓ (видит только ABC)
LLMProvider          ← бизнес-контракт: stream() / complete_json() / estimate_tokens()
   ↓
HttpProvider         ← склейка transport + codec
   ↓
LLMTransport         ← httpx.AsyncClient, base_url, auth, pool
   ↓
WireCodec            ← строит request body, парсит вендорские SSE-чанки → StreamEvent
   ↓
ProviderProfile      ← TOML-конфиг: vendor, wire_protocol, model, transport
```

**Ключевой принцип:** `codec` привязан к `wire_protocol`, а НЕ к вендору. Ollama, vLLM, LM Studio, LiteLLM, локальный mock → все имеют `wire_protocol = "openai_chat"` и используют тот же `OpenAIChatCodec`. Различие — только в `transport.base_url` и `auth_kind`.

### 18.2. Wire-протоколы

```python
WireProtocol = Literal[
    "openai_chat",                # /v1/chat/completions, SSE, OpenAI/Ollama/vLLM/LiteLLM
    "openai_responses",           # /v1/responses, новый API OpenAI с native JSON Schema
    "anthropic_messages",         # /v1/messages, native tool_use, ephemeral cache_control
    "google_generate_content",    # generativelanguage / vertex, partial JSON chunks
]

AuthKind = Literal[
    "none",                       # локальный mock, открытый vLLM
    "bearer",                     # Authorization: Bearer <token> — OpenAI, vLLM
    "api_key_header",             # x-api-key: <key> — Anthropic
    "google_key_query",           # ?key=<key> — старый Gemini
    "oauth_pkce",                 # OAuth с refresh-flow — Google Vertex
]
```

### 18.3. Pydantic-схема

```python
class TransportConfig(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)
    base_url: HttpUrl
    auth_kind: AuthKind = "none"
    api_key: SecretStr | None = None
    api_key_header: str | None = None         # требуется при auth_kind="api_key_header"
    extra_headers: dict[str, SecretStr] = Field(default_factory=dict)
    extra_cookies: dict[str, SecretStr] = Field(default_factory=dict)
    timeout_s: PositiveFloat = 120.0
    max_connections: PositiveInt = 32
    max_keepalive: PositiveInt = 16
    verify_tls: bool = True                    # False только для localhost-mock-ов

    @model_validator(mode="after")
    def _validate_auth(self) -> "TransportConfig":
        if self.auth_kind in {"bearer", "api_key_header"} and self.api_key is None:
            raise ValueError(f"api_key required for auth_kind={self.auth_kind}")
        if self.auth_kind == "api_key_header" and not self.api_key_header:
            raise ValueError("api_key_header (the header name) required when auth_kind=api_key_header")
        return self

class ProviderProfile(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)
    id: str = Field(pattern=r"^[a-z][a-z0-9_-]{1,31}$")
    vendor: Literal["anthropic", "openai", "google", "ollama", "vllm", "litellm", "custom"]
    wire_protocol: WireProtocol
    model_id: str
    display_name: str
    pricing: PricingPolicy | None = None       # если None → не считаем cost для этого профиля
    transport: TransportConfig
    capabilities: ProviderCapabilities = Field(default_factory=ProviderCapabilities)

class ProviderCapabilities(BaseModel):
    model_config = ConfigDict(frozen=True)
    supports_tools: bool = True
    supports_structured_output: bool = True
    supports_streaming: bool = True
    supports_prompt_cache: bool = False
    context_window: PositiveInt = 128_000
```

### 18.4. WireCodec — Protocol + реализации

```python
class WireCodec(Protocol):
    wire_protocol: ClassVar[WireProtocol]

    def build_request(
        self, req: ProviderRequest, profile: ProviderProfile,
    ) -> tuple[str, dict[str, object]]:
        """Возвращает (path_suffix, json_body). Path относительно transport.base_url."""

    async def decode_stream(
        self, response: httpx.Response, meta: CallerMeta,
    ) -> AsyncIterator[StreamEvent]:
        """Конвертирует вендорские SSE-чанки в унифицированные StreamEvent."""
```

Реализации: `OpenAIChatCodec`, `OpenAIResponsesCodec`, `AnthropicMessagesCodec`, `GoogleGenerateContentCodec`. Каждый — отдельный файл в `providers/codecs/`. Регистрация:

```python
@register_codec("openai_chat")
class OpenAIChatCodec: ...
```

### 18.5. HttpProvider — единственная реализация LLMProvider

```python
class HttpProvider(LLMProvider):
    def __init__(self, profile: ProviderProfile, client: httpx.AsyncClient, codec: WireCodec) -> None:
        self._profile = profile
        self._client = client
        self._codec = codec
        self._tokenizer = TokenizerFor(profile.wire_protocol, profile.model_id)

    async def stream(
        self, *, system, messages, tools=(), response_schema=None,
        max_tokens=4096, temperature=0.2, meta: CallerMeta,
    ) -> AsyncIterator[StreamEvent]:
        req = ProviderRequest(
            model=self._profile.model_id,
            system=system, messages=list(messages),
            tools=list(tools), response_schema=response_schema,
            max_tokens=max_tokens, temperature=temperature, meta=meta,
        )
        path, body = self._codec.build_request(req, self._profile)
        async with self._client.stream("POST", path, json=body) as resp:
            resp.raise_for_status()
            async for ev in self._codec.decode_stream(resp, meta):
                yield ev
```

### 18.6. ProviderFactory — один AsyncClient на профиль

```python
class ProviderFactory:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._clients: dict[str, httpx.AsyncClient] = {}
        self._codecs: dict[WireProtocol, WireCodec] = load_registered_codecs()

    def create(self, provider_id: str) -> HttpProvider:
        profile = self._settings.providers[provider_id]
        client = self._clients.get(provider_id) or self._build_client(profile)
        self._clients[provider_id] = client
        codec = self._codecs[profile.wire_protocol]
        return HttpProvider(profile, client, codec)

    def _build_client(self, profile: ProviderProfile) -> httpx.AsyncClient:
        cfg = profile.transport
        headers = {k: v.get_secret_value() for k, v in cfg.extra_headers.items()}
        cookies = {k: v.get_secret_value() for k, v in cfg.extra_cookies.items()}
        if cfg.auth_kind == "bearer":
            headers["Authorization"] = f"Bearer {cfg.api_key.get_secret_value()}"
        elif cfg.auth_kind == "api_key_header":
            headers[cfg.api_key_header] = cfg.api_key.get_secret_value()
        return httpx.AsyncClient(
            base_url=str(cfg.base_url),
            headers=headers,
            cookies=cookies,
            timeout=httpx.Timeout(cfg.timeout_s),
            limits=httpx.Limits(
                max_connections=cfg.max_connections,
                max_keepalive_connections=cfg.max_keepalive,
            ),
            verify=cfg.verify_tls,
            http2=True,
        )

    async def aclose(self) -> None:
        for c in self._clients.values():
            await c.aclose()
```

**Правила использования:**
1. Никогда не мутируй `client.headers`/`client.cookies` после создания — поломаешь параллельные запросы. Per-request метаданные (correlation-id, trace-id) передавай в `client.stream("POST", path, headers={...}, ...)`.
2. Один AsyncClient на `provider_id`. НЕ создавай клиент на каждый `stream()`.
3. `http2=True` обязателен — для всех трёх вендоров (и для Ollama) даёт multiplexing.
4. `verify_tls=False` разрешён ТОЛЬКО для `base_url` начинающихся с `http://localhost`, `http://127.0.0.1`, `http://0.0.0.0`. ProviderFactory валидирует это.

### 18.7. Конфиг в `~/.ivycode/config.toml`

```toml
# Облачные вендоры
[providers.claude]
id = "claude"
vendor = "anthropic"
wire_protocol = "anthropic_messages"
model_id = "claude-opus-4-7"
display_name = "Claude Opus 4.7"

[providers.claude.transport]
base_url = "https://api.anthropic.com/"
auth_kind = "api_key_header"
api_key_header = "x-api-key"
api_key = { env = "ANTHROPIC_API_KEY" }     # подтянется из env, не хранится в файле

[providers.gpt]
id = "gpt"
vendor = "openai"
wire_protocol = "openai_responses"
model_id = "gpt-5.5-xhigh"
display_name = "GPT-5.5 xhigh"

[providers.gpt.transport]
base_url = "https://api.openai.com/v1/"
auth_kind = "bearer"
api_key = { env = "OPENAI_API_KEY" }

# Локальный Ollama — нулевая стоимость, нативно совместим
[providers.local_llama]
id = "local_llama"
vendor = "ollama"
wire_protocol = "openai_chat"
model_id = "llama3.1:70b-instruct-q4_K_M"
display_name = "Llama 3.1 70B (local)"

[providers.local_llama.transport]
base_url = "http://localhost:11434/v1/"
auth_kind = "none"
verify_tls = false
timeout_s = 600                              # локальные модели медленнее на CPU/слабом GPU

# vLLM на корпоративном GPU-сервере
[providers.corp_qwen]
id = "corp_qwen"
vendor = "vllm"
wire_protocol = "openai_chat"
model_id = "Qwen/Qwen2.5-Coder-32B-Instruct"
display_name = "Qwen2.5 Coder 32B (corp)"

[providers.corp_qwen.transport]
base_url = "https://gpu-01.corp.internal/v1/"
auth_kind = "bearer"
api_key = { env = "CORP_VLLM_TOKEN" }
```

В CLI: `ivycode chat -m claude -m gpt -m local_llama` — три модели в одном фиде, две облачные + одна локальная, и Router/SubAgent об этом не знают.

---

## 19. Local Gateway (опционально, **строго ограниченный scope**)

ivycode поставляется с встроенным `ivycode gateway serve` — локальный FastAPI-сервер, который служит **единой точкой OpenAI-compatible API** для всех бэкендов. Это полезно когда:
- хочется один `base_url` для всех агентов независимо от вендора;
- нужна централизованная очередь/rate-limit на аккаунт;
- нужны метрики и логирование запросов в одном месте;
- хочется горячо переключать модели без рестарта CLI.

**Запрещённые сценарии (не поддерживаются и не будут):**
- Скрейп Web UI ChatGPT / Claude / Gemini через Playwright.
- JA3/JA4 spoofing, stealth-плагины, обход bot detection.
- Импорт токенов из чужих CLI-клиентов без явного opt-in пользователя.
- «Имитация человеческой активности» для keep-alive web-сессий.

Это нарушение ToS вендоров (OpenAI, Anthropic, Google) и инженерно нежизнеспособно — каждое обновление веб-морды ломает магию. Gateway будет работать ИСКЛЮЧИТЕЛЬНО с документированными API: облачные вендоры с API-ключами + локальные/self-hosted (Ollama, vLLM, LiteLLM).

### 19.1. Архитектура

```
ivycode CLI
   ↓ HttpProvider(base_url=http://localhost:7878/v1/)
[Local Gateway :7878]
   ├─ /v1/chat/completions      ← OpenAI-compatible вход
   ├─ /v1/models                ← list of configured backends
   ├─ /v1/health
   │
   ├─ AccountScheduler          ← per-backend Semaphore + Queue
   │     · backend "claude"  → Semaphore(2) Queue(maxsize=32)
   │     · backend "ollama"  → Semaphore(1) Queue(maxsize=8)
   │
   ├─ BackendAdapter            ← маршрутизация по `model` в запросе
   │     · model="claude-*"     → AnthropicAdapter (official API)
   │     · model="gpt-*"        → OpenAIAdapter (official API)
   │     · model="llama3.1:*"   → OllamaAdapter
   │     · model="Qwen/*"       → VLLMAdapter
   │
   ├─ StreamBridge              ← конвертация вендорских стримов → OpenAI SSE
   └─ AuthVault                 ← OS keychain (macOS Keychain / libsecret / Win Cred Manager)
```

### 19.2. Реализация ядра

```python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

app = FastAPI(title="ivycode-gateway", version=__version__)

@app.post("/v1/chat/completions")
async def chat_completions(req: OpenAIChatRequest) -> StreamingResponse:
    backend = backend_router.resolve(req.model)               # Backend
    job = ChatJob(request=req, span=current_span())
    await backend.scheduler.enqueue(job)                      # backpressure через bounded Queue

    async def sse() -> AsyncIterator[bytes]:
        async with backend.semaphore:                         # rate-limit на аккаунт
            async for chunk in backend.adapter.stream(job.request):
                yield f"data: {chunk.model_dump_json()}\n\n".encode()
            yield b"data: [DONE]\n\n"

    return StreamingResponse(sse(), media_type="text/event-stream")
```

### 19.3. SessionSupervisor (для OAuth-backends, если применимо)

Используется только когда backend требует OAuth refresh-flow (например, Google Vertex с service account JWT, или внутренние корпоративные OAuth-провайдеры). НЕ для web-сессий ChatGPT/Claude/Gemini.

Базируется на каркасе из ответа другой LLM (см. предыдущее сообщение):

```python
class SessionState(StrEnum):
    FRESH = "fresh"
    STALE = "stale"
    NEEDS_REAUTH = "needs_reauth"
    DEGRADED = "degraded"

class SessionSupervisor:
    """
    Адаптивный refresh документированного OAuth refresh-token flow.
    При >=3 неудачах подряд → NEEDS_REAUTH, останов очереди, явный сигнал в UI.
    """
    def __init__(self, adapter: AuthAdapter, store: KeychainStore, policy: RefreshPolicy):
        self._adapter = adapter           # реализует RFC 6749/9700 refresh_token flow
        self._store = store               # OS keychain через `keyring`
        self._policy = policy
        # ... остальной код как в эталоне выше, с честным NEEDS_REAUTH
```

Все секреты — через `keyring` (macOS Keychain, libsecret на Linux, Windows Credential Manager), НИКОГДА не в файлах.

### 19.4. Активация

Gateway **выключен по умолчанию**. Включается явно:

```bash
ivycode gateway init        # создаёт ~/.ivycode/gateway/config.toml
ivycode gateway serve       # запускает на 127.0.0.1:7878
```

После запуска в `config.toml` появляется новый профиль:

```toml
[providers.gateway]
id = "gateway"
vendor = "custom"
wire_protocol = "openai_chat"
model_id = "auto"                          # роутится gateway-ом по model header
display_name = "Local Gateway"

[providers.gateway.transport]
base_url = "http://localhost:7878/v1/"
auth_kind = "none"
verify_tls = false
```

И в `ivycode chat -m gateway` все запросы идут через локальный gateway.

---

## 20. Understand-Anything (опциональный plugin)

[Understand-Anything](https://github.com/Lum1104/Understand-Anything) (MIT) — LLM-обогащённый граф знаний кодовой базы + интерактивный web-дашборд. Дополняет нативный CodeGraph там, где AST-парсинг недостаточен (семантические описания, cross-language связи через документацию, hot-paths из git-истории).

**Включается по opt-in через onboarding wizard** (см. §21).

### 20.1. Что добавляется

| Skill | Display verb | Описание |
|---|---|---|
| `understand_explain` | `Explain` | LLM-разбор файла или модуля с архитектурным комментарием |
| `understand_diff` | `Diff` | Анализ git-changes с точки зрения impact + риска |
| `open_dashboard` | `Dashboard` | Открывает web-дашборд графа в браузере |

### 20.2. Архитектура интеграции

```
ivycode/
└── plugins/
    └── understand_anything/
        ├── __init__.py
        ├── manifest.toml           # объявление плагина, зависимостей, skills
        ├── service.py              # фасад над node-процессом UA
        ├── skills.py               # @skill-обёртки
        └── enrichment.py           # подмешивает UA-описания в SymbolBrief
```

`manifest.toml`:

```toml
[plugin]
name = "understand-anything"
version = "0.1.0"
source = "github:Lum1104/Understand-Anything"
license = "MIT"

[plugin.requirements]
node = ">=20.0.0"
pnpm = ">=9.0.0"

[plugin.skills]
understand_explain = "ivycode.plugins.understand_anything.skills:explain"
understand_diff = "ivycode.plugins.understand_anything.skills:diff"
open_dashboard = "ivycode.plugins.understand_anything.skills:open_dashboard"

[plugin.enrichments]
codegraph.symbol_brief = "ivycode.plugins.understand_anything.enrichment:enrich_symbol"
```

### 20.3. Жизненный цикл

```
ivycode init understand-anything
  → проверка node>=20 и pnpm; если нет → инструкция установки
  → git clone в ~/.ivycode/plugins/understand-anything/
  → pnpm install
  → npx understand-anything analyze --root $PROJECT_ROOT
       → пишет .understand-anything/knowledge-graph.json в проекте
  → enrichment.py подгружает knowledge-graph.json в кеш
  → CodeGraphService.snapshot_for() при наличии плагина дополнительно
    обогащает SymbolBrief.docstring_summary из UA, если AST-docstring отсутствует
```

При reindex (watchdog обнаружил FS-событие) — UA анализ запускается ТОЛЬКО для затронутых файлов, не для всего проекта. Это даёт inkremental cost.

### 20.4. Cost-warning при включении

В onboarding wizard явно показывается:

```
▏ ✦  understand-anything

▏  This plugin adds LLM-enriched code graph + web dashboard.
▏  It uses tree-sitter + LLM to generate semantic descriptions
▏  for every symbol in your project.

▏  Cost estimate for ~/code/myapp (1,247 symbols):
▏    initial enrichment   ~$0.40   (one-time)
▏    per-file reindex     ~$0.01   (on save)
▏    total est. monthly   ~$3-8    (typical dev usage)

▏  Requires: node>=20, pnpm>=9
▏  Adds skills: Explain · Diff · Dashboard

▏  [Y] enable now  [N] skip  [L] more info
```

---

## 21. Onboarding wizard (первый запуск)

Триггер: `ivycode chat` в директории без `~/.ivycode/projects/{sha(cwd)}.toml`.

Шаги:

```
Step 1/5: providers
  ▏ Detected env vars: ANTHROPIC_API_KEY, OPENAI_API_KEY
  ▏ Configure GEMINI_API_KEY? [Y/n/skip]

Step 2/5: default models
  ▏ Choose primary models (space to toggle, Enter to confirm):
  ▏   [x] claude-opus-4-7
  ▏   [x] gpt-5.5-xhigh
  ▏   [ ] gemini-2.5-pro
  ▏   [ ] llama3.1:70b (requires Ollama on localhost:11434)

Step 3/5: CodeGraph
  ▏ Index ~/code/myapp now? (~5s for 247 files) [Y/n]

Step 4/5: Understand-Anything plugin (optional)
  ▏ [card from §20.4]

Step 5/5: theme
  ▏ Confirm Quiet Luxury theme? [Y/customize]
```

Каждый шаг можно skip, результат пишется в `~/.ivycode/projects/{sha(cwd)}.toml`. Повторный запуск wizard: `ivycode init --reconfigure`.

---

## 22. Обновлённый Definition of Done

К §13 добавляется:

9. `ivycode gateway serve` запускается, `/v1/chat/completions` принимает запросы, Ollama-backend работает end-to-end на localhost.
10. `ivycode init understand-anything` корректно отказывает с инструкцией, если нет Node/pnpm; при наличии — устанавливает и регистрирует skills.
11. `ivycode chat -m local_llama` (Ollama) работает без интернета.
12. Welcome screen рендерится корректно при `IVYCODE_MOTION=static`.
13. Все системные сообщения проходят linter `tools/voice_lint.py` (regex-проверка соответствия §17.8 лексикону).
14. `IVYCODE_THEME=high-contrast` переключает палитру на WCAG AAA.

---

## 23. SessionSupervisor → EventBus → UI

### 23.1. Граница допустимости адаптера (runtime-gate)

В §19 зафиксирован запрет на автоматизацию Web UI ChatGPT / Claude / Gemini. На уровне runtime это обеспечивается реестром адаптеров `AdapterRegistry`:

```python
class AdapterRegistry:
    _ALLOWED: Final[dict[str, type[AuthorizedAutomationAdapter]]] = {
        "ollama":           OllamaAdapter,
        "vllm":             VLLMAdapter,
        "litellm":          LiteLLMAdapter,
        "anthropic_api":    AnthropicOfficialAdapter,
        "openai_api":       OpenAIOfficialAdapter,
        "google_api":       GoogleOfficialAdapter,
        "internal_rpa":     InternalRPAAdapter,        # требует консент-файл
    }
    _FORBIDDEN_HOST_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
        re.compile(r"(^|\.)chatgpt\.com$"),
        re.compile(r"(^|\.)claude\.ai$"),
        re.compile(r"(^|\.)gemini\.google\.com$"),
        re.compile(r"(^|\.)bard\.google\.com$"),
    )

    @classmethod
    def build(cls, kind: str, profile: AdapterProfile) -> AuthorizedAutomationAdapter:
        if kind not in cls._ALLOWED:
            raise UnauthorizedAdapterError(f"adapter kind={kind!r} is not in the allowlist")
        for host in profile.target_hosts:
            if any(p.search(host) for p in cls._FORBIDDEN_HOST_PATTERNS):
                raise UnauthorizedAdapterError(
                    f"adapter target host {host!r} matches consumer Web UI; "
                    f"use the vendor's official API instead (see §19)"
                )
        if kind == "internal_rpa":
            if not (profile.consent_file and profile.consent_file.exists()):
                raise UnauthorizedAdapterError(
                    "internal_rpa requires explicit consent_file (operator-signed grant)"
                )
        return cls._ALLOWED[kind](profile)
```

`UnauthorizedAdapterError` поднимается на стадии `GatewayPipeline.start()` и приводит к чёткой ошибке в UI: пользователь видит, что именно не разрешено и какая альтернатива.

### 23.2. Pydantic-события session-lifecycle

Все переходы `SessionSupervisor._mark()` публикуются в общий `EventBus` (см. §1.2). Тип события:

```python
class SessionEventKind(StrEnum):
    STATE_CHANGED      = "session.state_changed"     # любой переход
    BECAME_FRESH       = "session.fresh"
    BECAME_STALE       = "session.stale"
    BECAME_DEGRADED    = "session.degraded"
    BECAME_NEEDS_REAUTH = "session.needs_reauth"
    PROBE_FAILED       = "session.probe_failed"
    REFRESH_OK         = "session.refresh_ok"
    REFRESH_FAILED     = "session.refresh_failed"

class SessionEvent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    kind: SessionEventKind
    account_id: str
    adapter_kind: str
    previous_state: SessionState
    next_state: SessionState
    snapshot_generation: int | None = None
    expires_at_epoch_s: float | None = None
    reason: str | None = None
    failures_in_a_row: int = 0
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    meta: CallerMeta                                  # agent=ROUTER, model=ModelRef("custom", "gateway", ...)
```

### 23.3. Патч `SessionSupervisor._mark()` для публикации

В исходный класс `SessionSupervisor` (предоставленный код) добавляется одна зависимость и одна строка в `_mark`:

```python
class SessionSupervisor:
    def __init__(
        self,
        adapter: AuthorizedAutomationAdapter,
        store: SessionStore,
        event_bus: EventBus,                          # <— добавлено
        account_id: str,                              # <— добавлено
        adapter_kind: str,                            # <— добавлено
        policy: RefreshPolicy = RefreshPolicy(),
    ) -> None:
        ...
        self._bus = event_bus
        self._account_id = account_id
        self._adapter_kind = adapter_kind

    async def _mark(self, state: SessionState, snapshot: SessionSnapshot | None) -> None:
        previous = self._state
        async with self._state_changed:
            self._state = state
            self._snapshot = snapshot
            self._state_changed.notify_all()
        if previous != state:
            await self._bus.publish(SessionEvent(
                kind=_STATE_TO_KIND[state],
                account_id=self._account_id,
                adapter_kind=self._adapter_kind,
                previous_state=previous,
                next_state=state,
                snapshot_generation=snapshot.generation if snapshot else None,
                expires_at_epoch_s=snapshot.expires_at_epoch_s if snapshot else None,
                failures_in_a_row=self._failures,
                meta=self._caller_meta(),
            ))
```

EventBus (`core/event_bus.py`) — типизированный pub/sub поверх `asyncio.Queue` с фильтрацией по типу события:

```python
class EventBus:
    def __init__(self) -> None:
        self._subscribers: defaultdict[type, list[asyncio.Queue[BaseModel]]] = defaultdict(list)

    def subscribe(self, event_type: type[T], *, maxsize: int = 256) -> AsyncIterator[T]:
        q: asyncio.Queue[T] = asyncio.Queue(maxsize=maxsize)
        self._subscribers[event_type].append(q)
        async def gen() -> AsyncIterator[T]:
            try:
                while True:
                    yield await q.get()
            finally:
                self._subscribers[event_type].remove(q)
        return gen()

    async def publish(self, event: BaseModel) -> None:
        for q in self._subscribers[type(event)]:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                # медленный подписчик — дропаем самое старое, чтобы не блокировать публикатора
                _ = q.get_nowait()
                q.put_nowait(event)
```

### 23.4. Подписчик в `status_bar.py`

Status bar (см. §17.7) получает новый 5-й сегмент **только** когда состояние не `FRESH`. В `FRESH` режиме сегмент полностью отсутствует — не отвлекает.

```python
class StatusBar:
    def __init__(self, bus: EventBus, theme: Theme) -> None:
        self._bus = bus
        self._theme = theme
        self._session_indicator: SessionIndicator | None = None
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        self._task = asyncio.create_task(self._consume(), name="statusbar-session-consumer")

    async def _consume(self) -> None:
        async for ev in self._bus.subscribe(SessionEvent):
            if ev.next_state is SessionState.FRESH:
                self._session_indicator = None
            else:
                self._session_indicator = SessionIndicator(
                    state=ev.next_state,
                    account_id=ev.account_id,
                    adapter_kind=ev.adapter_kind,
                    failures=ev.failures_in_a_row,
                )

    def render(self) -> Text:
        segments: list[Text] = [
            self._render_model_agent(),
            self._render_graph(),
            self._render_context_bar(),
        ]
        if self._session_indicator:
            segments.append(self._render_session())          # 4-й сегмент вытесняет hotkey hints
        else:
            segments.append(self._render_hotkeys())
        return Text(" · ").join(segments)

    def _render_session(self) -> Text:
        ind = self._session_indicator
        style, glyph, label = {
            SessionState.STALE:        (self._theme.warn,  "◐", "session stale"),
            SessionState.DEGRADED:     (self._theme.warn,  "◑", f"session degraded (×{ind.failures})"),
            SessionState.NEEDS_REAUTH: (self._theme.error, "●", "session needs reauth"),
        }[ind.state]
        text = Text.assemble((f"{glyph} ", style), (label, f"bold {style}"))
        if ind.state is SessionState.NEEDS_REAUTH:
            text.append("  press /reauth", style="dim italic")
        return text
```

### 23.5. Подписчик в `activity_panel.py`

Activity-панель (правый верх sidebar) логирует каждый переход одной строкой по канону Precision (см. §17.8):

```
✦ session  ·  fresh → stale         · probe_failed
✦ session  ·  stale → degraded      · ×2 failures
✦ session  ·  degraded → needs_reauth
```

Реализация:

```python
class ActivityPanel:
    def __init__(self, bus: EventBus, theme: Theme, max_lines: int = 12) -> None:
        self._lines: deque[ActivityLine] = deque(maxlen=max_lines)
        self._theme = theme
        self._bus = bus

    async def _consume_sessions(self) -> None:
        async for ev in self._bus.subscribe(SessionEvent):
            self._lines.append(ActivityLine(
                glyph="✦", source="session",
                text=f"{ev.previous_state} → {ev.next_state}"
                     + (f" · {ev.reason}" if ev.reason else "")
                     + (f" · ×{ev.failures_in_a_row} failures" if ev.failures_in_a_row else ""),
                style=self._style_for(ev.next_state),
                timestamp=ev.occurred_at,
            ))
```

### 23.6. NEEDS_REAUTH diagnostic card в чат-фиде

Когда `EventBus` публикует `SessionEvent(next_state=NEEDS_REAUTH)`, `ChatFeed` дополнительно вставляет inline diagnostic card по канону §17.9 (Inline diagnostic card, левый красный бар).

Шаблон карточки:

```
▏ ⚠  reauth required · adapter=ollama · account=local-01     14:32
▏
▏  the upstream session requires explicit re-authentication.
▏  reason: refreshed token failed probe (3 failures in a row)
▏
▏  ┌─ next steps ──────────────────────────────────────────────┐
▏  │  [R] /reauth     · open browser for OAuth re-consent      │
▏  │  [S] /model      · switch to another configured provider  │
▏  │  [P] /pause      · suspend gateway queue                  │
▏  │  [T] toggle stacktrace                                    │
▏  └───────────────────────────────────────────────────────────┘
▏
▏  ━━ input disabled until reauth or model switch ━━
```

Конструкция Pydantic-события для карточки:

```python
def reauth_card_from(ev: SessionEvent) -> ErrorEvent:
    return ErrorEvent(
        component="transport",
        code="reauth_required",
        summary=f"adapter={ev.adapter_kind} · account={ev.account_id}",
        cause=ev.reason or f"{ev.failures_in_a_row} failures in a row",
        recovery_actions=[
            RecoveryAction(hotkey="R", label="/reauth · open browser for OAuth re-consent", command="session.reauth"),
            RecoveryAction(hotkey="S", label="/model · switch to another configured provider", command="session.switch_model"),
            RecoveryAction(hotkey="P", label="/pause · suspend gateway queue",                 command="gateway.pause"),
            RecoveryAction(hotkey="T", label="toggle stacktrace",                              command="ui.toggle_stack"),
        ],
        meta=ev.meta,
    )
```

### 23.7. Блокировка ввода и backpressure

При `NEEDS_REAUTH`:

1. `InputController` подписан на `SessionEvent` и переключается в `disabled` режим: `prompt_toolkit` `PromptSession.app.current_buffer.read_only = True`, prompt-индикатор меняется с `>` на `⊘`, появляется hint в footer (см. §23.4).
2. `GatewayPipeline.submit()` начинает поднимать `ReauthRequired` мгновенно (без enqueue), чтобы клиентский WireCodec видел причину, а не таймаут.
3. **Уже находящиеся в очереди job-ы** не отменяются автоматически — пользователь нажимает `[P] pause`, либо хоткей `Ctrl+X`, который вызывает `GatewayPipeline.cancel_pending()` (helper из патча §23.8).
4. После успешного `/reauth` (см. §23.8) — состояние возвращается в `FRESH`, `EventBus` публикует `BECAME_FRESH`, `InputController` снимает блокировку, footer-сегмент исчезает, diagnostic card в фиде получает append-строку `→ resolved at HH:MM:SS`.

### 23.8. Дополнения к `GatewayPipeline`

Добавляются три helper-метода (нужны для UI-команд из карточки):

```python
class GatewayPipeline:
    async def pause(self) -> None:
        self._paused.set()                           # worker_loop ждёт self._paused.wait()
    async def resume(self) -> None:
        self._paused.clear()
    async def cancel_pending(self) -> int:
        cancelled = 0
        while True:
            try:
                job = self._queue.get_nowait()
            except asyncio.QueueEmpty:
                return cancelled
            job.cancel_event.set()
            await job.fail(ReauthRequired("cancelled by user"))
            self._queue.task_done()
            cancelled += 1
    async def trigger_reauth(self) -> None:
        snap = await self._adapter.open_or_recover_context(snapshot=None)
        if snap is None:
            raise ReauthRequired("adapter did not return a session snapshot")
        # supervisor сам опубликует BECAME_FRESH при следующем probe
        await self._supervisor._refresh_once()
```

---

## 24. FastAPI wrapper для шлюза

### 24.1. Структура файлов

```
ivycode/gateway/
├── __init__.py
├── app.py                  # FastAPI application factory
├── lifespan.py             # startup/shutdown — старт SessionSupervisor, GatewayPipeline
├── schemas.py              # Pydantic-модели входа (OpenAI-compatible)
├── routes/
│   ├── __init__.py
│   ├── chat.py             # POST /v1/chat/completions
│   ├── models.py           # GET /v1/models
│   └── health.py           # GET /v1/health, GET /v1/session
├── middleware/
│   ├── __init__.py
│   ├── errors.py           # global exception handler
│   ├── correlation.py      # trace-id propagation
│   └── auth.py             # Bearer-токен локального gateway (опц.)
└── pipeline.py             # содержит код из исходного сообщения (SessionSupervisor, GatewayPipeline, …)
```

### 24.2. Входные схемы (OpenAI-compatible)

```python
class OpenAIChatMessage(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    role: Literal["system", "user", "assistant", "tool"]
    content: str | list[dict[str, object]]
    name: str | None = None
    tool_call_id: str | None = None

class OpenAIChatCompletionsRequest(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    model: Annotated[str, Field(min_length=1, max_length=200)]
    messages: list[OpenAIChatMessage] = Field(min_length=1, max_length=200)
    stream: bool = True
    temperature: Annotated[float, Field(ge=0, le=2)] = 0.2
    max_tokens: Annotated[int, Field(ge=1, le=128_000)] = 4096
    tools: list[dict[str, object]] = Field(default_factory=list)
    user: str | None = None                      # OpenAI-conv: end-user id для tracking

    def to_chat_request(self) -> ChatRequest:
        return ChatRequest(
            model=self.model,
            messages=[m.model_dump(exclude_none=True) for m in self.messages],
            stream=self.stream,
            temperature=self.temperature,
        )
```

### 24.3. Application factory + lifespan

```python
def create_app(settings: GatewaySettings) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        bus = EventBus()
        adapter = AdapterRegistry.build(settings.adapter_kind, settings.adapter_profile)
        store = JsonSessionStore(settings.session_state_path)
        supervisor = SessionSupervisor(
            adapter=adapter,
            store=store,
            event_bus=bus,
            account_id=settings.account_id,
            adapter_kind=settings.adapter_kind,
            policy=RefreshPolicy(),
        )
        pipeline = GatewayPipeline(
            supervisor=supervisor,
            adapter=adapter,
            queue_maxsize=settings.queue_maxsize,
        )
        await pipeline.start()
        app.state.pipeline = pipeline
        app.state.bus = bus
        app.state.settings = settings
        try:
            yield
        finally:
            await pipeline.stop()

    app = FastAPI(
        title="ivycode-gateway",
        version=__version__,
        lifespan=lifespan,
        default_response_class=JSONResponse,
        docs_url=None if settings.disable_docs else "/docs",
    )
    app.add_middleware(CorrelationIdMiddleware)
    if settings.bearer_token:
        app.add_middleware(LocalBearerAuthMiddleware, token=settings.bearer_token)
    register_exception_handlers(app)
    app.include_router(chat.router,   prefix="/v1")
    app.include_router(models.router, prefix="/v1")
    app.include_router(health.router, prefix="/v1")
    return app
```

### 24.4. POST /v1/chat/completions

```python
router = APIRouter(tags=["chat"])

@router.post("/chat/completions")
async def chat_completions(
    request: OpenAIChatCompletionsRequest,
    pipeline: GatewayPipeline = Depends(get_pipeline),
    correlation_id: str = Depends(get_correlation_id),
) -> Response:
    if not request.stream:
        # Не поддерживаем non-streaming на v1: ivycode CLI всегда стримит. 
        # Полная буферизация смысла не имеет для архитектуры FanOut/FanIn.
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "stream_required",
                              "message": "this gateway only supports stream=true"}},
        )

    try:
        job = await pipeline.submit(request.to_chat_request())
    except GatewayQueueFull as exc:
        raise HTTPException(
            status_code=429,
            detail={"error": {"code": "queue_full",
                              "message": str(exc),
                              "retry_after_s": 2}},
            headers={"Retry-After": "2"},
        ) from exc
    except ReauthRequired as exc:
        # Состояние NEEDS_REAUTH — мгновенный отказ без enqueue
        raise HTTPException(
            status_code=401,
            detail={"error": {"code": "reauth_required",
                              "message": str(exc)}},
        ) from exc

    async def body() -> AsyncIterator[bytes]:
        async for chunk in job.stream_sse():
            yield chunk

    return StreamingResponse(
        body(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",                  # для прокси, отключает буферизацию
            "X-Correlation-Id": correlation_id,
            "Connection": "keep-alive",
        },
    )

def get_pipeline(req: Request) -> GatewayPipeline:
    return req.app.state.pipeline

def get_correlation_id(req: Request) -> str:
    return req.headers.get("x-correlation-id") or uuid.uuid4().hex
```

### 24.5. GET /v1/models и /v1/health и /v1/session

```python
@models_router.get("/models")
async def list_models(pipeline: GatewayPipeline = Depends(get_pipeline)) -> dict[str, object]:
    backends = pipeline.list_backends()
    return {
        "object": "list",
        "data": [
            {"id": b.model_id, "object": "model", "owned_by": b.vendor,
             "created": int(b.registered_at.timestamp())}
            for b in backends
        ],
    }

@health_router.get("/health")
async def health(pipeline: GatewayPipeline = Depends(get_pipeline)) -> dict[str, object]:
    return {
        "status": "ok" if pipeline.supervisor.state is SessionState.FRESH else "degraded",
        "session_state": pipeline.supervisor.state.value,
        "queue_depth": pipeline.queue_depth(),
        "queue_maxsize": pipeline.queue_maxsize,
    }

@health_router.post("/session/reauth")
async def trigger_reauth(pipeline: GatewayPipeline = Depends(get_pipeline)) -> dict[str, str]:
    """
    Вызывается CLI-командой /reauth. Открывает браузер adapter-ом для
    официального OAuth-consent либо повторной authorized RPA-сессии.
    """
    await pipeline.trigger_reauth()
    return {"status": "reauth_started"}
```

### 24.6. Global Exception Middleware

```python
def register_exception_handlers(app: FastAPI) -> None:

    @app.exception_handler(ReauthRequired)
    async def _on_reauth(_: Request, exc: ReauthRequired) -> JSONResponse:
        return JSONResponse(
            status_code=401,
            content={"error": {"type": "session_error", "code": "reauth_required",
                               "message": str(exc)}},
        )

    @app.exception_handler(TransientSessionError)
    async def _on_transient(_: Request, exc: TransientSessionError) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={"error": {"type": "session_error", "code": "session_degraded",
                               "message": str(exc), "retry_after_s": 5}},
            headers={"Retry-After": "5"},
        )

    @app.exception_handler(GatewayQueueFull)
    async def _on_queue_full(_: Request, exc: GatewayQueueFull) -> JSONResponse:
        return JSONResponse(
            status_code=429,
            content={"error": {"type": "rate_limit_error", "code": "queue_full",
                               "message": str(exc), "retry_after_s": 2}},
            headers={"Retry-After": "2"},
        )

    @app.exception_handler(UnauthorizedAdapterError)
    async def _on_forbidden_adapter(_: Request, exc: UnauthorizedAdapterError) -> JSONResponse:
        return JSONResponse(
            status_code=403,
            content={"error": {"type": "configuration_error", "code": "adapter_not_allowed",
                               "message": str(exc)}},
        )

    @app.exception_handler(ValidationError)
    async def _on_pydantic(_: Request, exc: ValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"error": {"type": "invalid_request_error", "code": "schema_invalid",
                               "message": "request payload failed validation",
                               "details": exc.errors(include_url=False)}},
        )

    @app.exception_handler(Exception)
    async def _on_unhandled(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("gateway.unhandled", extra={"err_type": type(exc).__name__})
        return JSONResponse(
            status_code=500,
            content={"error": {"type": "internal_error", "code": "unhandled",
                               "message": "internal gateway error"}},
        )
```

**Inside-stream errors.** Когда исключение случилось ПОСЛЕ начала стрима (HTTP-заголовки уже отправлены — HTTPException бесполезен), `GatewayJob.fail(exc)` отправляет финальный SSE-чанк `data: {"error": ...}` с тем же error-формой, что выше, плюс корректный `data: [DONE]`. Клиентский codec (см. §25) обязан различать pre-stream и mid-stream ошибки.

### 24.7. Запуск

```bash
ivycode gateway init
ivycode gateway serve --host 127.0.0.1 --port 7878        # биндим только loopback по умолчанию
```

Под капотом — `uvicorn ivycode.gateway.app:create_app(settings) --factory` с graceful shutdown по SIGTERM / SIGINT, который дёргает `lifespan` → `pipeline.stop()` → корректно дренирует in-flight стримы.

---

## 25. Клиентский WireCodec для локального шлюза (CLI ↔ Gateway)

Шлюз отдаёт OpenAI-compatible SSE. Значит на клиентской стороне **существующий `OpenAIChatCodec` (§18.4) переиспользуется как есть** — никакого отдельного wire-протокола. Различия только два:

1. Маппинг шлюзовых error-codes (`reauth_required`, `queue_full`, `session_degraded`) в типизированные `StreamEvent(kind="error", error_message=...)` и далее в `ErrorEvent` (§17.9 / §23.6).
2. Per-request `X-Correlation-Id` для сопоставления CLI-trace и gateway-trace в логах.

### 25.1. Конфигурация профиля для шлюза

```toml
[providers.gateway]
id = "gateway"
vendor = "custom"
wire_protocol = "openai_chat"
model_id = "auto"                        # шлюз сам роутит по полю model в payload
display_name = "Local Gateway"

[providers.gateway.transport]
base_url = "http://127.0.0.1:7878/v1/"
auth_kind = "bearer"                     # опционально, если LocalBearerAuthMiddleware включён
api_key = { env = "IVYCODE_GATEWAY_TOKEN" }
verify_tls = false                       # разрешено — host=127.0.0.1
timeout_s = 600
max_connections = 16
max_keepalive = 8
```

### 25.2. Расширение `OpenAIChatCodec` для шлюзовых ошибок

В исходный класс добавляется один новый case в `decode_stream`:

```python
class OpenAIChatCodec:
    wire_protocol: ClassVar[WireProtocol] = "openai_chat"

    def build_request(self, req: ProviderRequest, profile: ProviderProfile) -> tuple[str, dict[str, object]]:
        body: dict[str, object] = {
            "model": profile.model_id if profile.model_id != "auto" else req.model,
            "messages": req.messages,
            "stream": True,
            "temperature": req.temperature,
            "max_tokens": req.max_tokens,
        }
        if req.tools:
            body["tools"] = req.tools
        if req.response_schema is not None:
            body["response_format"] = {"type": "json_schema",
                                       "json_schema": {"name": "response",
                                                       "schema": req.response_schema,
                                                       "strict": True}}
        return "chat/completions", body

    async def decode_stream(
        self, response: httpx.Response, meta: CallerMeta,
    ) -> AsyncIterator[StreamEvent]:
        async for line in response.aiter_lines():
            if not line or not line.startswith("data: "):
                continue
            raw = line.removeprefix("data: ").strip()
            if raw == "[DONE]":
                yield StreamEvent(kind="stop", meta=meta)
                return
            chunk = json.loads(raw)

            # ── шлюзовые ошибки (mid-stream) ──────────────────────────
            if (err := chunk.get("error")) is not None:
                yield StreamEvent(
                    kind="error",
                    error_message=err.get("message", "upstream error"),
                    meta=meta.model_copy(update={"tool_name": f"gateway.{err.get('code', 'unknown')}"}),
                )
                yield StreamEvent(kind="stop", meta=meta)
                return

            choices = chunk.get("choices") or []
            if not choices:
                continue
            delta = choices[0].get("delta") or {}

            if (text := delta.get("content")) and isinstance(text, str):
                yield StreamEvent(kind="delta", text_delta=text, meta=meta)

            for tc in delta.get("tool_calls") or []:
                # Tool-call delta-формат OpenAI: id + index + function.{name,arguments}
                fn = tc.get("function") or {}
                if (name := fn.get("name")):
                    yield StreamEvent(
                        kind="tool_call_start",
                        tool_call=ToolCall(id=tc["id"], name=name, arguments={}),
                        meta=meta,
                    )
                if (args := fn.get("arguments")):
                    yield StreamEvent(kind="tool_call_args_delta",
                                      args_delta=args, meta=meta)

            if choices[0].get("finish_reason"):
                yield StreamEvent(kind="tool_call_end", meta=meta) \
                    if delta.get("tool_calls") else \
                    StreamEvent(kind="stop", meta=meta)
```

### 25.3. Обработка pre-stream HTTP-ошибок

`HttpProvider.stream()` (§18.5) уже вызывает `resp.raise_for_status()` сразу после `async with self._client.stream(...)`. Для шлюза мы оборачиваем это в типизированный маппер:

```python
class HttpProvider:
    async def stream(self, *, system, messages, tools=(), response_schema=None,
                     max_tokens=4096, temperature=0.2, meta: CallerMeta,
                    ) -> AsyncIterator[StreamEvent]:
        req = ProviderRequest(...)
        path, body = self._codec.build_request(req, self._profile)
        request_headers = {"X-Correlation-Id": str(meta.trace_id)}
        try:
            async with self._client.stream("POST", path, json=body, headers=request_headers) as resp:
                if resp.status_code >= 400:
                    detail = await self._read_error(resp)
                    raise GatewayHttpError(status=resp.status_code, detail=detail, meta=meta)
                async for ev in self._codec.decode_stream(resp, meta):
                    yield ev
        except GatewayHttpError as exc:
            yield StreamEvent(kind="error", error_message=exc.user_message,
                              meta=meta.model_copy(update={"tool_name": f"gateway.{exc.code}"}))
            yield StreamEvent(kind="stop", meta=meta)

    @staticmethod
    async def _read_error(resp: httpx.Response) -> dict[str, object]:
        try:
            payload = await resp.aread()
            return json.loads(payload).get("error", {})
        except (json.JSONDecodeError, ValueError):
            return {"code": "non_json", "message": resp.reason_phrase}
```

`GatewayHttpError` транслируется в `ErrorEvent` (§17.9) с конкретным набором `recovery_actions`:

```python
_HTTP_TO_RECOVERY: Final[dict[str, tuple[RecoveryAction, ...]]] = {
    "reauth_required": (
        RecoveryAction(hotkey="R", label="/reauth · re-authenticate session", command="session.reauth"),
        RecoveryAction(hotkey="S", label="/model · switch provider",          command="session.switch_model"),
    ),
    "queue_full": (
        RecoveryAction(hotkey="W", label="wait & retry in 2s",  command="provider.retry_after"),
        RecoveryAction(hotkey="S", label="/model · switch provider", command="session.switch_model"),
    ),
    "session_degraded": (
        RecoveryAction(hotkey="W", label="wait & retry in 5s",  command="provider.retry_after"),
        RecoveryAction(hotkey="P", label="/pause · suspend gateway", command="gateway.pause"),
    ),
    "adapter_not_allowed": (
        RecoveryAction(hotkey="O", label="open §19 docs",       command="docs.open_section_19"),
    ),
}
```

### 25.4. Connection pooling & cancellation contract

1. **Один `httpx.AsyncClient` на профиль `gateway`** — создаётся `ProviderFactory._build_client()` (§18.6), переиспользуется для всех `HttpProvider.stream()` параллельных вызовов. `http2=True` обязателен — мультиплексирует все параллельные стримы поверх одного TCP-коннекта.
2. **Limits.** `max_connections=16`, `max_keepalive=8` — шлюз сидит на loopback, можно держать пул узким.
3. **Cancellation.** Когда пользователь жмёт `Ctrl+C` в CLI, `asyncio.TaskGroup` (§7.1) кенселит задачу-стрим. `httpx.AsyncClient.stream()` корректно закрывает TCP-стрим при выходе из `async with`. На стороне gateway это попадает в `job.stream_sse()` → `CancelledError` → `job.cancel_event.set()` → `_worker_loop` выходит из `run_chat` через `cancel_event` контракт adapter-а. Никакой полу-висящей работы.
4. **Idempotency.** Шлюз НЕ дедуплицирует запросы. CLI обязан считать каждый submit как новый. Retry после ошибки (`[R]` / `[W]`) генерирует новый `trace_id` + новый submit.

### 25.5. Тест-кейс end-to-end

В `tests/integration/test_gateway_roundtrip.py`:

```python
@pytest.mark.asyncio
async def test_e2e_chat_through_local_gateway(gateway_with_ollama: GatewayHandle) -> None:
    profile = ProviderProfile(
        id="gateway", vendor="custom", wire_protocol="openai_chat",
        model_id="auto", display_name="Local Gateway",
        transport=TransportConfig(base_url=gateway_with_ollama.url, auth_kind="none",
                                  verify_tls=False, timeout_s=120),
    )
    factory = ProviderFactory(Settings(providers={"gateway": profile}))
    provider = factory.create("gateway")

    meta = CallerMeta(agent=AgentName.ROUTER, model=ModelRef(
        provider=ProviderName.GOOGLE,  # любая, для теста
        model_id="llama3.1:8b-instruct",
        display_name="Llama 3.1 8B"))

    chunks: list[StreamEvent] = []
    async for ev in provider.stream(
        system="you are a senior python engineer",
        messages=[Message(role=Role.USER, content="say hello in one word", meta=meta)],
        meta=meta,
    ):
        chunks.append(ev)

    assert any(c.kind == "delta" and c.text_delta for c in chunks)
    assert chunks[-1].kind == "stop"

    await factory.aclose()
```

### 25.6. Resulting flow (sequence)

```
CLI: ivycode chat "fix login.py"
  Router.handle()
    └─ ProviderFactory.create("gateway")
       └─ HttpProvider.stream(meta)
          └─ httpx.AsyncClient.stream("POST", "chat/completions", json={...},
                                       headers={"X-Correlation-Id": trace_id})
             ↓
GATEWAY: POST /v1/chat/completions
  pipeline.submit(ChatRequest) → GatewayJob
  worker_loop:
    async with semaphore(1):
       supervisor.ensure_usable() → SessionSnapshot
       adapter.run_chat(snapshot, request, cancel_event)
          ↓ yields StreamDelta(content="…")
       job.emit(SseMessage(OpenAIChatSSECodec.delta(...)))
  Response: text/event-stream
             ↑
CLI: OpenAIChatCodec.decode_stream(response, meta)
   yields StreamEvent(kind="delta", text_delta="…")
   ChatFeed.on_event() → MessagePanel buffer growth → Live redraw
```

---

— *Конец спецификации.*
