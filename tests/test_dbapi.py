import types

import pytest

from gaussdb_sqlalchemy import dbapi


def test_dbapi_connect_delegates_to_gaussdb_module(monkeypatch):
    module = types.SimpleNamespace()

    def connect(*args, **kwargs):
        return {"args": args, "kwargs": kwargs}

    module.connect = connect
    monkeypatch.setattr(dbapi, "import_module", lambda name: module)

    assert dbapi.connect("dsn", user="scott") == {
        "args": ("dsn",),
        "kwargs": {"user": "scott"},
    }


def test_dbapi_getattr_delegates_constants(monkeypatch):
    module = types.SimpleNamespace(apilevel="2.0", paramstyle="pyformat")
    monkeypatch.setattr(dbapi, "import_module", lambda name: module)

    assert dbapi.apilevel == "2.0"
    assert dbapi.paramstyle == "pyformat"


def test_dbapi_getattr_raises_attribute_error_for_unknown_names(monkeypatch):
    module = types.SimpleNamespace()
    monkeypatch.setattr(dbapi, "import_module", lambda name: module)

    with pytest.raises(AttributeError):
        dbapi.not_a_real_dbapi_attribute
