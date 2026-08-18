from __future__ import annotations

from modules.sqlalchemy_compat import CoreCursor


class ResultThatClosesOnLastrowid:
    returns_rows = True
    rowcount = 2

    def __init__(self):
        self.closed = False

    @property
    def lastrowid(self):
        self.closed = True
        return 0

    def __iter__(self):
        if self.closed:
            raise RuntimeError('cursor is closed')
        return iter([])


class FakeConnection:
    def __init__(self):
        self.result = ResultThatClosesOnLastrowid()

    def execute(self, _statement, _bind):
        return self.result


def test_select_does_not_read_lastrowid_before_materializing_rows(monkeypatch):
    monkeypatch.setattr('modules.sqlalchemy_compat._guard_core_sql', lambda sql, params: sql)
    monkeypatch.setattr('modules.sqlalchemy_compat.normalize_sql_for_engine', lambda sql: sql)
    monkeypatch.setattr('modules.sqlalchemy_compat.convert_qmark_sql', lambda sql, params: (sql, {}))
    cursor = CoreCursor(FakeConnection())

    result = cursor.execute('SELECT 1')

    assert result.fetchall() == []
    assert cursor.connection.result.closed is False

