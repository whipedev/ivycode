# Skills UX/UI Improvements — v0.5.0

> Аудит UX/UI слоя skills в ivycode CLI и план улучшений.
> Базовая ревизия: `v0.5.0-skills-foundation`.
> Источник истины: `PROMPT_SPEC.md` §4 (UX/UI спецификация Rich).

---

## 0. Контекст

Архитектурно skills-слой чистый: декоратор `@skill` + `SkillRegistry` + `SkillRuntime` + `PluginStore`. Контракт между LLM и Python-callable сделан корректно — JSON Schema генерируется через Pydantic, permissions объявляются явно.

Проблема в **UX-слое**: текущая реализация `ivycode/cli/app.py` находится на уровне «работает», а не на уровне «Cyberpunk × Quiet Luxury», заявленном в спеке. Identity-глифы из `theme.py` (`◆ ▲ ● ✦ ✧`) не используются в skills-плоскости, спиннеры из §4.5 не подключены, error-панели из §4.4 отсутствуют.

---

## 1. Проблемы (детальный список)

### 1.1. `skills list` — нет колонки Description

**Файл:** `ivycode/cli/app.py:209-220`

Таблица показывает `Skill | Permissions | Status`. Описание уже хранится в `SkillDefinition.description`, но не выводится. Пользователь видит `fs.read_file` без понимания, что это.

**Status сейчас лжёт:** `_status_for` (app.py:247-254) хардкодит строки по совпадению префикса имени — это ложная телеметрия. Все skills фактически `ready`, отличаются они уровнем риска, а не статусом.

### 1.2. `inspect` дампит JSON Schema сырьём

**Файл:** `ivycode/cli/app.py:109-117`

`console.print_json(json.dumps(definition.parameters_schema))` — это «простыня» с `$defs`, `properties`, `required`, которую пользователь должен парсить глазами. Skill — это контракт; контракт нужно показывать как **таблицу параметров**, а не как JSON-дамп.

Нарушает Hick's Law: одновременно ~10 структурных полей schema против ожидаемых 2-4 для принятия решения «как вызвать».

### 1.3. `skills run` — нулевой UX

**Файл:** `ivycode/cli/app.py:120-128`

- Нет спиннера/`Status` во время `await _invoke_skill` → **нарушение инварианта §0.5** («операция >50 мс → `Live`/`Status`»).
- Нет заголовка «какой skill вызван, с какими args».
- Нет длительности, отметки об успехе.
- Один и тот же сырой JSON и для пайпов, и для человека — нет `--json` vs human output.

### 1.4. Нет error-UX

**Файл:** `ivycode/skills/builtins/fs.py:25-29`, `ivycode/skills/registry.py:71`

Если skill кидает `ValueError`/`KeyError`/`PermissionError`, наружу полетит сырой traceback Typer/Python. Спека §4.4 рисует ошибки как `✗` красным с разворачиваемой stacktrace-нодой — этого нет.

### 1.5. `skills save` пишет в `~/.ivycode/plugins` без confirmation

**Файл:** `ivycode/cli/app.py:131-152`

Global-state-операция без подтверждения. Опечатка в `slug` = осиротевший каталог в `~/.ivycode/plugins/`. Нет `--yes` / `--dry-run`. Нет проверки существующего slug **до** вызова `_plugin_store().save_plugin`, поэтому `FileExistsError` выглядит как сырое исключение.

### 1.6. `--arg key=value` — слабая валидация

**Файл:** `ivycode/cli/app.py:257-274`

`_parse_arg_value` понимает только `bool` / `int` / `string`. Будущие массивы и dict-параметры не пройдут. Главное — **нет валидации против `parameters_schema` до вызова skill**: ошибка типа всплывёт изнутри handler-а как Pydantic-исключение без полезного контекста.

### 1.7. Permissions показаны фразами, без бейджей

**Файл:** `ivycode/cli/app.py:237-244`

`_human_permissions` — движение в правильную сторону, но фраза «can search the local code graph» съест ширину таблицы при 5+ скиллах. Нужны компактные бейджи-чипы: `[GRAPH·R]`, `[FS·R]`, `[FS·W]` — цветом по тяжести (W = `warn`, R = `text_dim`).

### 1.8. Identity-глифы не используются для skills

**Файл:** `ivycode/ui/theme.py` (есть `◆ ▲ ● ✦ ✧`, нет skill-namespace глифов)

У skill-namespace нет визуальной подписи. Согласно §4.7 принцип «один глиф на сущность» должен распространяться на skills:

| Namespace | Глиф |
|---|---|
| `fs.*` | `▤` |
| `graph.*` | `◈` |
| `plugin.*` | `✦` |

Глиф ставится в первую колонку таблицы перед именем — мгновенная категоризация без курсорной читки.

### 1.9. Dashboard — застывшая «следующая подсказка»

**Файл:** `ivycode/cli/app.py:181-183`

`suggested next action` хардкодится одной строкой. Должна реагировать на состояние:

- Skills есть, plugins пусто → «попробуйте `ivycode skills inspect fs.read_file`»
- Inspect был, save пуст → «`ivycode skills save <slug> --skill fs.read_file`»
- Plugins есть → «`ivycode skills run fs.read_file --arg file_path=README.md`»

### 1.10. `plugins` — слепая выкладка

**Файл:** `ivycode/cli/app.py:223-234`

Только `slug | skills`. `PluginManifest` хранит `description`, `created_by`, `manifest_version` — ничего не выводится. Нет:

- пути плагина (хотя в `save` он показан);
- даты создания (поле в манифесте отсутствует — добавить);
- статуса `valid/broken` (если skill из манифеста больше не зарегистрирован).

### 1.11. Help-тексты бедны

**Файл:** `ivycode/cli/app.py` (все Typer-команды)

Только однострочные docstring. Нет:

- `epilog=...` с примерами вызова;
- `rich_help_panel="Inspection"` vs `rich_help_panel="Plugins"` для группировки.

При росте до 10+ команд `--help` станет свалкой.

### 1.12. `_stage_boundary` использует тот же канал, что и валидный вывод

**Файл:** `ivycode/cli/app.py:30-35`

`chat` / `plan` пишут `style="yellow"` в обычный console — визуально неотличимо от warning-сообщения. Должно быть `Panel` с `warn`-бордером и подсказкой «эта команда появится в следующей версии».

---

## 2. План изменений (приоритизированный)

| # | Изменение | Файлы | Эффект | Приоритет |
|---|---|---|---|---|
| 1 | Добавить колонку Description в `skills list` + убрать ложный `Status` | `cli/app.py:209` | моментальная читабельность | **P0** |
| 2 | Спиннер `ivy-orbit` (§4.5) вокруг `_invoke_skill` + панель результата | `cli/app.py:120-128` | соответствие §0.5/§4.5 | **P0** |
| 3 | Pretty-`inspect`: таблица параметров вместо JSON-дампа | `cli/app.py:109-117` | Hick's Law / Miller's Law | **P0** |
| 4 | `Confirm` на `skills save` + проверка существующего slug заранее | `cli/app.py:131-152` | защита от ошибок | **P0** |
| 5 | Error-panel с `✗` и красным бордером для исключений skill | новый `ui/panels/error_panel.py` | §4.4 | **P1** |
| 6 | Валидация `--arg` против `parameters_schema` до вызова | `cli/app.py:120-128` | понятные ошибки | **P1** |
| 7 | Бейджи permissions в таблице вместо длинных фраз | `cli/app.py:237-244` + `ui/theme.py` | плотность таблицы | **P1** |
| 8 | Глифы namespace в первой колонке (`▤ fs.read_file`) | `ui/theme.py`, `cli/app.py` | identity по §4.7 | **P2** |
| 9 | `--json` / `--plain` флаги для `run` и `list` | `cli/app.py` | scriptability | **P2** |
| 10 | Динамический `suggested next action` в dashboard | `cli/app.py:164-185` | onboarding | **P2** |
| 11 | `plugins` — расширенная таблица (description, path, valid?) | `cli/app.py:223-234`, `skills/store.py` | observability | **P2** |
| 12 | `rich_help_panel` группировка + `epilog` примеры | `cli/app.py` (все Typer-команды) | discoverability | **P3** |
| 13 | `_stage_boundary` через `Panel` с `warn`-бордером | `cli/app.py:30-35` | визуальная семантика | **P3** |

---

## 3. Решения по дизайну

### 3.1. Декоратор `@skill` — расширение

Текущий декоратор объявляет только `name`/`description`/`permissions`. Для честной семантики `Status` в UI нужны новые поля:

```python
@skill(
    name="fs.write_file",
    description="Write a project file inside the current project root.",
    permissions=["fs:write"],
    risk="write",                    # read | write | destructive
    requires_confirmation=False,     # для destructive по умолчанию True
    idempotent=False,
)
```

Эти поля попадут в `SkillMetadata` → `SkillDefinition` → таблицу `list` как бейдж риска, а не как высосанная из имени строка.

### 3.2. `ivycode skills list` — целевой рендер

```
ivycode skills · 5 builtins

  glyph  name                  description                          permissions       risk
  ─────  ────────────────────  ───────────────────────────────────  ────────────────  ──────
  ▤      fs.read_file          Read a project file (line range op…  [FS·R]            read
  ▤      fs.write_file         Write a project file inside root.    [FS·R] [FS·W]    write
  ◈      graph.search_symbols  Search code symbols by name.         [GRAPH·R]         read
  ◈      graph.get_impact_…    Find callers for a symbol.           [GRAPH·R]         read
  ◈      graph.get_framewo…    List framework routes.               [GRAPH·R]         read
```

- Глиф = namespace (`▤` для `fs.*`, `◈` для `graph.*`).
- Description — обрезается до ширины колонки.
- Permissions — компактные бейджи: `[FS·R]` `text_dim`, `[FS·W]` `warn` цвет.
- Risk — бейдж: `read` `text_dim`, `write` `warn`, `destructive` `error`.

### 3.3. `ivycode skills inspect <name>` — целевой рендер

```
ivycode skill · fs.write_file
Write a project file inside the current project root.

permissions
  [FS·R] can read files inside this project
  [FS·W] can write files inside this project

parameters
  name        type   required  default  description
  ──────────  ─────  ────────  ───────  ──────────────────────────────
  file_path   str    yes       —        relative or absolute path
  content     str    yes       —        file content to write

usage
  ivycode skills run fs.write_file --arg file_path=docs/note.md --arg content="hello"
```

JSON-схема показывается только под флагом `--schema`.

### 3.4. `ivycode skills run <name>` — целевой рендер

```
▰▱ running fs.read_file · file_path=README.md
✓ fs.read_file · 12ms

# ivycode

…file content here, syntax-highlighted if it's code…
```

- `Status` с кастомным спиннером `ivy-orbit` (§4.5) во время `await`.
- Заголовок с args.
- Длительность.
- Markdown/Syntax-рендер если результат — `str` файла; таблица если `list[SymbolBrief]`; JSON-дерево если dict.
- `--json` флаг → строго `console.print_json(...)`, ничего больше.

### 3.5. Error-panel

Новый файл `ivycode/ui/panels/error_panel.py`:

```python
@dataclass(frozen=True)
class ErrorPanel:
    skill_name: str
    exception: BaseException
    arguments: dict[str, object]

    def render(self) -> RenderableType:
        # Panel с border=PALETTE.error
        # Title: "✗ {skill_name} failed"
        # Body: type(exception).__name__, str(exception)
        # Подсказка remediation в зависимости от типа исключения
        # Traceback — свёрнут, разворачивается флагом --traceback
        ...
```

### 3.6. Confirmation на `save`

```python
if (store.plugin_root / slug).exists():
    raise typer.BadParameter(f"plugin already exists: {slug}")

console.print(f"will save plugin '{slug}' with skills: {', '.join(selected)}")
console.print(f"target: {store.plugin_root / slug}", style="dim")
if not typer.confirm("proceed?", default=False):
    raise typer.Abort()
```

Плюс флаг `--yes` для скриптинга.

---

## 4. Что НЕ нужно делать

- **Не превращать `inspect` в Markdown-страницу.** Skill — это контракт; нужна плотная таблица, не лонгрид.
- **Не вводить emoji в UI skills.** Спека §4.1 запрещает (исключение — «celebration»-зона).
- **Не дробить `skills` на дальнейшие подкоманды** типа `skills permissions list`. Иерархия уже двухуровневая; Hick's Law на пределе.
- **Не заменять Rich Table на Tree** для `list`. Tree оправдан только в §4.4 для tool-call лога; для каталога skills таблица плотнее и сравниваемее.
- **Не делать `run` интерактивным wizard-ом** с prompt-ами на каждый параметр. Это сломает скриптинг; интерактивность остаётся за интерактивным режимом `chat`.

---

## 5. Definition of Done для v0.5.0

- [ ] P0 пункты (#1-#4) реализованы и покрыты pytest-ами под `tests/cli/test_skills_ui.py`.
- [ ] P1 пункты (#5-#7) реализованы.
- [ ] `mypy --strict` проходит без warnings.
- [ ] `ivycode skills list` визуально совпадает с §3.2.
- [ ] `ivycode skills inspect fs.write_file` совпадает с §3.3.
- [ ] `ivycode skills run` обёрнут в `Status` со спиннером `ivy-orbit`.
- [ ] Все exceptions из skills проходят через `ErrorPanel`.
- [ ] `skills save` требует `Confirm` (или `--yes`) и проверяет slug заранее.
- [ ] Скриншоты целевого рендера зафиксированы в `docs/screenshots/skills-v0.5.0/`.

---

## 6. Дальнейшие шаги (за пределами v0.5.0)

- **v0.6.0:** plugin discovery (`ivycode skills install <git-url>`), цифровая подпись manifest-а.
- **v0.6.0:** интеграция skills UI с Activity-панелью (§4.2) — стрим вызовов skills в реальном времени из chat-сессии.
- **v0.7.0:** policy engine — skill требует `Approval` от пользователя при первом вызове в проекте (по аналогии с Claude Code permissions).
