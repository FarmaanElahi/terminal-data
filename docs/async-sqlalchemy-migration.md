# Plan: Migrate to Full Async SQLAlchemy

## Context

All FastAPI routes are `async def` but the database layer is sync (`create_engine`, `Session`). FastAPI runs sync DB calls in a thread pool — this works but wastes threads under load. This migration replaces the sync engine with `create_async_engine` + `AsyncSession` + `psycopg_async` driver throughout every service, router, and background engine.

---

## Phase 1 — Foundation (everything depends on these 5 files)

### 1. `src/terminal/config.py`
Add `async_database_url` property — replaces `+psycopg` with `+psycopg_async` in the URL:
```python
@property
def async_database_url(self) -> str:
    if self.db_scheme.startswith("sqlite"):
        return self.database_url  # no sqlite async support needed
    return self.database_url.replace(
        f"+{self.db_driver}://", f"+{self.db_driver}_async://"
    )
```

### 2. `src/terminal/database/core.py`
- Replace `create_engine` → `create_async_engine(settings.async_database_url, ...)`
- **No global sync engine** — connections are lazy; no threads/connections created at import time
- Use `async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)` as `AsyncSessionLocal`
- `get_session` commits on success, rolls back on exception, always closes

```python
engine = create_async_engine(settings.async_database_url, pool_size=10, max_overflow=20,
    pool_pre_ping=True, pool_recycle=3600, connect_args={"options": "-c statement_timeout=30000"})
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    session = AsyncSessionLocal()
    session_id = SessionTracker.track_session(session)
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        SessionTracker.untrack_session(session_id)
        await session.close()
```

### 3. `src/terminal/database/manage.py`
Create its own local sync engine (only instantiated when `init_db`/`drop_db` are called):
```python
def _make_sync_engine(engine_input=None):
    if engine_input:
        return engine_input
    from sqlalchemy import create_engine
    return create_engine(settings.database_url, ...)
```
This is only ever invoked from CLI (`terminal database init`) — never during server operation.

### 4. `src/terminal/database/__init__.py`
Export `AsyncSessionLocal` in addition to current exports. Remove `engine` from export if not needed externally.

### 5. `src/terminal/dependencies.py`
- Change `get_session` return type to `AsyncGenerator[AsyncSession, None]`
- Delegate to `db_get_session()` via `async for` (or just use it directly)
- Remove `from sqlalchemy.orm import Session` → `from sqlalchemy.ext.asyncio import AsyncSession`

---

## Phase 2 — Service Files (all independent, apply same transformation)

**Universal transformation rules:**

| Sync | Async |
|---|---|
| `def fn(session: Session, ...)` | `async def fn(session: AsyncSession, ...)` |
| `session.execute(stmt)` | `await session.execute(stmt)` |
| `(result).scalars().first()` | `(await session.execute(stmt)).scalars().first()` |
| `session.get(Model, id)` | `await session.get(Model, id)` |
| `session.add(obj)` | `session.add(obj)` — NOT awaited |
| `session.delete(obj)` | `await session.delete(obj)` |
| `session.commit()` | `await session.commit()` |
| `session.flush()` | `await session.flush()` |
| `session.refresh(obj)` | `await session.refresh(obj)` |
| `from sqlalchemy.orm import Session` | `from sqlalchemy.ext.asyncio import AsyncSession` |

**Note:** `session.scalars(stmt)` shorthand does NOT exist on `AsyncSession` — always use `(await session.execute(stmt)).scalars()`.

Files to transform (same pattern, apply uniformly):
- `src/terminal/auth/service.py`
- `src/terminal/preferences/service.py`
- `src/terminal/broker/service.py`
- `src/terminal/lists/service.py` (note: `get_symbols` called from `get_symbols_async` — both become async)
- `src/terminal/charts/service.py` (note: `upsert_study_template` calls `get_study_template` internally — must `await` internal call)
- `src/terminal/column/service.py` (note: `update` calls `get` internally)
- `src/terminal/condition/service.py` (same as column)
- `src/terminal/alerts/service.py` (largest: 15+ functions, also `clear_alert_logs` uses `delete()` statement)
- `src/terminal/formula/service.py` (note: `create` and `delete` call `get` internally — must await)

---

## Phase 3 — Router Files

**Universal transformation:**
- `def` → `async def` for any sync endpoints
- `session: Session = Depends(get_session)` → `session: AsyncSession = Depends(get_session)`
- All service calls get `await`
- Update imports

**Special cases:**
- `broker/router.py`: Has **direct** `session.commit()` and `session.delete(credential)` in router body (not via service) — these must be awaited too.
- `health/router.py`: Uses `engine.connect()` synchronously — change to:
  ```python
  async with engine.connect() as conn:
      await conn.execute(text("SELECT 1"))
  ```

Files:
- `src/terminal/auth/router.py` — already async, just await service calls + update type hints
- `src/terminal/preferences/router.py` — `def` → `async def`
- `src/terminal/broker/router.py` — already async; also await direct session ops
- `src/terminal/lists/router.py` — already async, await service calls
- `src/terminal/charts/router.py` — `def` → `async def`
- `src/terminal/column/router.py` — `def` → `async def`
- `src/terminal/condition/router.py` — `def` → `async def`
- `src/terminal/alerts/router.py` — `def` → `async def`
- `src/terminal/formula/router.py` — `def` → `async def`
- `src/terminal/notifications/router.py` — `def` → `async def`
- `src/terminal/market_feed/router.py` — already async, await service calls if any
- `src/terminal/health/router.py` — fix engine.connect() pattern

---

## Phase 4 — AlertEngine (critical: runs outside request lifecycle)

**File:** `src/terminal/alerts/engine.py`

Currently imports `from terminal.database.core import engine as db_engine` and creates `Session(db_engine)` at 3 call sites (lines 225, 494, 538).

**Changes:**
1. Remove `from sqlalchemy.orm import Session` and `from terminal.database.core import engine as db_engine`
2. Add `from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker`
3. Update `__init__` to accept `session_factory: async_sessionmaker`
4. Convert 3 sync session blocks to `async with self._session_factory() as session:` with `await` on all DB calls
5. `_load_alerts_from_db` stays a regular method but becomes `async def` (called from `start()`)

**File:** `src/terminal/main.py` — pass `AsyncSessionLocal` when constructing AlertEngine:
```python
from terminal.database.core import AsyncSessionLocal
alert_engine = AlertEngine(manager, session_factory=AsyncSessionLocal)
```

---

## Phase 5 — Infrastructure

### `src/terminal/database/revisions/env.py` (Alembic)
Use `sync_engine` — Alembic migrations are inherently sync. No async Alembic needed:
```python
from terminal.database.core import sync_engine
config.set_main_option("sqlalchemy.url", settings.database_url)

def run_migrations_online():
    with sync_engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
```

### `src/terminal/cli.py`
The health check uses `engine.connect()` — switch to `sync_engine`:
```python
from terminal.database.core import sync_engine
with sync_engine.connect() as conn:
    conn.execute(text("SELECT 1"))
```

---

## Phase 6 — Tests

**File:** `tests/conftest.py`

- `session_fixture`: Change to `@pytest_asyncio.fixture`, build async URL (`+psycopg_async`), use `create_async_engine` + `async_sessionmaker`, yield `AsyncSession`, rollback and drop tables using `await conn.run_sync(Base.metadata.drop_all)`
- `client_fixture`: Change override to `async def get_session_override(): yield session`
- `init_db` table creation uses sync engine (just for setup) then disposes it

```python
@pytest_asyncio.fixture(name="session", scope="function")
async def session_fixture(postgres_container):
    sync_url = postgres_container.get_connection_url().replace("+psycopg2", "+psycopg")
    async_url = sync_url.replace("+psycopg", "+psycopg_async")

    from sqlalchemy import create_engine as _sync_create_engine
    _sync_e = _sync_create_engine(sync_url)
    init_db(_sync_e)
    _sync_e.dispose()

    test_engine = create_async_engine(async_url)
    TestSession = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)

    async with TestSession() as session:
        yield session
        await session.rollback()
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

    await test_engine.dispose()

@pytest_asyncio.fixture(name="client")
async def client_fixture(session):
    async def get_session_override():
        yield session
    ...
    api.dependency_overrides[get_session] = get_session_override
    ...
```

---

## Execution Order

```
Phase 1: config.py → database/core.py → database/manage.py → database/__init__.py → dependencies.py
Phase 2: All service files (can be done in parallel)
Phase 3: All router files (after services)
Phase 4: alerts/engine.py → main.py
Phase 5: alembic env.py → cli.py
Phase 6: tests/conftest.py
```

---

## Verification

1. Run `uv run fastapi dev src/terminal/main.py` — server should start without errors
2. Hit `/api/v1/health/ready` — database check should show `"status": "ok"`
3. Run `uv run pytest tests` — all tests should pass with async session fixture
4. Run `uv run terminal database upgrade` — Alembic migration should apply cleanly using sync_engine

## Unresolved Questions

None — approach is clear and fully mapped.
