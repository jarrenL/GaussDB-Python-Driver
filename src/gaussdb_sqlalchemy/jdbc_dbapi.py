"""Lazy DB-API bridge to JayDeBeApi for GaussDB JDBC connections."""

from __future__ import annotations

from datetime import date
from datetime import datetime
from importlib import import_module
from types import ModuleType
from typing import Any


_DBAPI_MODULE = "jaydebeapi"


def _load_dbapi() -> ModuleType:
    try:
        module = import_module(_DBAPI_MODULE)
        _patch_converters(module)
        return module
    except ModuleNotFoundError as exc:
        if exc.name == _DBAPI_MODULE:
            raise ModuleNotFoundError(
                "The JDBC bridge package is not installed. Install it with "
                "'pip install JayDeBeApi JPype1' or install this project with "
                "the 'jdbc' extra."
            ) from exc
        raise
    except ImportError as exc:
        raise ImportError(
            "JayDeBeApi is installed, but the JVM bridge could not be loaded. "
            "Install a supported Java Runtime and JPype1, then ensure java is "
            "available on PATH."
        ) from exc


def _patch_converters(module: ModuleType) -> None:
    if getattr(module, "_gaussdb_converters_patched", False):
        return
    if not hasattr(module, "_DEFAULT_CONVERTERS"):
        return

    module._DEFAULT_CONVERTERS["TIMESTAMP"] = _to_datetime
    module._DEFAULT_CONVERTERS["DATE"] = _to_date
    module._DEFAULT_CONVERTERS["BINARY"] = _to_binary
    module._DEFAULT_CONVERTERS["VARBINARY"] = _to_binary
    module._DEFAULT_CONVERTERS["LONGVARBINARY"] = _to_binary
    module._DEFAULT_CONVERTERS["BLOB"] = _to_binary
    module._DEFAULT_CONVERTERS["BOOLEAN"] = _to_boolean
    module._DEFAULT_CONVERTERS["BIT"] = _to_boolean

    converters = getattr(module, "_converters", None)
    jdbc_name_to_const = getattr(module, "_jdbc_name_to_const", None)
    if converters is not None and jdbc_name_to_const is not None:
        for name, converter in module._DEFAULT_CONVERTERS.items():
            type_const = jdbc_name_to_const.get(name)
            if type_const is not None:
                converters[type_const] = converter

    module._gaussdb_converters_patched = True


def _to_datetime(result_set, column):
    value = result_set.getTimestamp(column)
    if value is None:
        return None
    return _parse_jdbc_timestamp(str(value))


def _parse_jdbc_timestamp(text):
    if "." in text:
        text = text[:26]
    text = text.replace(" ", "T", 1)
    return datetime.fromisoformat(text)


def _to_date(result_set, column):
    value = result_set.getDate(column)
    if value is None:
        return None
    return date.fromisoformat(str(value)[:10])


def _to_binary(result_set, column):
    value = result_set.getBytes(column)
    if value is None:
        return None
    return bytes((int(byte) + 256) % 256 for byte in value)


def _to_boolean(result_set, column):
    value = result_set.getBoolean(column)
    if result_set.wasNull():
        return None
    return bool(value)


def connect(*args: Any, **kwargs: Any):
    """Open a JDBC connection using JayDeBeApi."""

    connection = _load_dbapi().connect(*args, **kwargs)
    jconn = getattr(connection, "jconn", None)
    if jconn is not None:
        jconn.setAutoCommit(False)
    return connection


def __getattr__(name: str) -> Any:
    return getattr(_load_dbapi(), name)


apilevel = "2.0"
threadsafety = 1
paramstyle = "qmark"
