from config import resolve_postgresql_url_from_environment


DATABASE_ENV_NAMES = (
    "DATABASE_URL", "DATABASE_PRIVATE_URL", "POSTGRES_URL", "POSTGRESQL_URL",
    "PGHOST", "PGPORT", "PGUSER", "PGPASSWORD", "PGDATABASE",
)


def _clear(monkeypatch):
    for name in DATABASE_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


def test_railway_database_url_is_normalized(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:secret@postgres.railway.internal:5432/railway")
    assert resolve_postgresql_url_from_environment() == (
        "postgresql+psycopg://user:secret@postgres.railway.internal:5432/railway"
    )


def test_railway_pg_variables_build_encoded_url(monkeypatch):
    _clear(monkeypatch)
    values = {
        "PGHOST": "postgres.railway.internal", "PGPORT": "5432",
        "PGUSER": "postgres", "PGPASSWORD": "p@ss:/ word",
        "PGDATABASE": "railway",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    assert resolve_postgresql_url_from_environment() == (
        "postgresql+psycopg://postgres:p%40ss%3A%2F%20word@postgres.railway.internal:5432/railway"
    )


def test_missing_railway_database_variables_returns_empty(monkeypatch):
    _clear(monkeypatch)
    assert resolve_postgresql_url_from_environment() == ""
