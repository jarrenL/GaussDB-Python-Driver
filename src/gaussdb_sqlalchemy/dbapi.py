"""Lazy DB-API bridge to Huawei's ``gaussdb`` package."""

from __future__ import annotations

from importlib import import_module
from types import ModuleType
from typing import Any


_DBAPI_MODULE = "gaussdb"


def _load_dbapi() -> ModuleType:
    try:
        return import_module(_DBAPI_MODULE)
    except ModuleNotFoundError as exc:
        if exc.name == _DBAPI_MODULE:
            raise ModuleNotFoundError(
                "The GaussDB DB-API package is not installed. Install it with "
                "'pip install gaussdb' or install this project normally so its "
                "runtime dependencies are resolved."
            ) from exc
        raise
    except ImportError as exc:
        raise ImportError(
            "The GaussDB DB-API package is installed, but no usable GaussDB "
            "client implementation was found. Install the GaussDB client "
            "libraries for your platform and ensure their bin/lib directory "
            "is available on PATH, LD_LIBRARY_PATH, or DYLD_LIBRARY_PATH."
        ) from exc


def connect(*args: Any, **kwargs: Any):
    """Open a GaussDB connection using Huawei's DB-API adapter."""

    return _load_dbapi().connect(*args, **kwargs)


def __getattr__(name: str) -> Any:
    return getattr(_load_dbapi(), name)
