"""In-memory stand-ins for asyncpg so DB-facing code runs without Postgres."""

from typing import Any, List, Tuple


class FakeConn:
    """Records every statement; `rows` feeds fetch/fetchrow/fetchval."""

    def __init__(self) -> None:
        self.calls: List[Tuple[str, str, Tuple[Any, ...]]] = []
        self.rows: List[Any] = []
        self.value: Any = None
        self.result = "UPDATE 1"

    def _log(self, kind: str, sql: str, args: Tuple[Any, ...]) -> None:
        self.calls.append((kind, " ".join(sql.split()), args))

    async def execute(self, sql: str, *args: Any) -> str:
        self._log("execute", sql, args)
        return self.result

    async def executemany(self, sql: str, rows: Any) -> None:
        self._log("executemany", sql, (list(rows),))

    async def fetch(self, sql: str, *args: Any) -> List[Any]:
        self._log("fetch", sql, args)
        return self.rows

    async def fetchrow(self, sql: str, *args: Any) -> Any:
        self._log("fetchrow", sql, args)
        return self.rows[0] if self.rows else None

    async def fetchval(self, sql: str, *args: Any) -> Any:
        self._log("fetchval", sql, args)
        return self.value

    def transaction(self) -> "FakeConn":
        return self

    async def __aenter__(self) -> "FakeConn":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        return None

    def sql(self, kind: str) -> List[str]:
        return [c[1] for c in self.calls if c[0] == kind]


class FakePool:
    def __init__(self) -> None:
        self.conn = FakeConn()

    def acquire(self) -> FakeConn:
        return self.conn

    async def close(self) -> None:
        return None
