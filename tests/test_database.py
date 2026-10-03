from app.db.session import _async_database_url


def test_neon_connection_url_uses_asyncpg_and_tls():
    url, connect_args = _async_database_url(
        "postgresql://user:password@ep-example.neon.tech/rag?sslmode=require&channel_binding=require"
    )

    assert url.drivername == "postgresql+asyncpg"
    assert "channel_binding" not in url.query
    assert connect_args == {"ssl": "require"}


def test_local_postgres_url_does_not_force_tls():
    url, connect_args = _async_database_url("postgresql://user:password@localhost/rag")

    assert url.drivername == "postgresql+asyncpg"
    assert connect_args == {}