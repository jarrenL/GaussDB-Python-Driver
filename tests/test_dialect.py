import sys
import types

import pytest
from sqlalchemy.engine import make_url

from gaussdb_sqlalchemy.dialect import GaussDBDialect_gaussdb
from gaussdb_sqlalchemy import dbapi as gaussdb_dbapi


def test_create_connect_args_maps_sqlalchemy_url_to_gaussdb_keywords():
    dialect = GaussDBDialect_gaussdb()

    args, kwargs = dialect.create_connect_args(
        make_url(
            "gaussdb+gaussdb://scott:tiger@db.example.com:8000/postgres"
            "?sslmode=verify-full&application_name=demo"
        )
    )

    assert args == []
    assert kwargs == {
        "host": "db.example.com",
        "port": 8000,
        "dbname": "postgres",
        "user": "scott",
        "password": "tiger",
        "sslmode": "verify-full",
        "application_name": "demo",
    }


def test_import_dbapi_loads_gaussdb_lazily(monkeypatch):
    module = types.ModuleType("gaussdb")

    def connect(*args, **kwargs):
        return args, kwargs

    module.connect = connect
    monkeypatch.setitem(sys.modules, "gaussdb", module)

    dbapi = GaussDBDialect_gaussdb.import_dbapi()

    assert dbapi.connect("dsn", autocommit=True) == (("dsn",), {"autocommit": True})


def test_import_dbapi_has_actionable_error_when_dependency_missing(monkeypatch):
    def missing_module(name):
        raise ModuleNotFoundError("No module named 'gaussdb'", name=name)

    monkeypatch.setattr(gaussdb_dbapi, "import_module", missing_module)

    with pytest.raises(ModuleNotFoundError, match="pip install gaussdb"):
        GaussDBDialect_gaussdb.import_dbapi().connect()


def test_import_dbapi_has_actionable_error_when_client_library_missing(monkeypatch):
    def missing_client(name):
        raise ImportError("no pq wrapper available")

    monkeypatch.setattr(gaussdb_dbapi, "import_module", missing_client)

    with pytest.raises(ImportError, match="client implementation"):
        GaussDBDialect_gaussdb.import_dbapi().connect()


def test_is_disconnect_uses_connection_state_and_messages():
    dialect = GaussDBDialect_gaussdb()

    assert dialect.is_disconnect(RuntimeError("ignored"), types.SimpleNamespace(closed=True), None)
    assert dialect.is_disconnect(RuntimeError("server closed the connection"), None, None)
    assert not dialect.is_disconnect(RuntimeError("syntax error"), None, None)
