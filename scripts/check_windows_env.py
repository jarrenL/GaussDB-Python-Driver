"""Check whether the local Python environment can load the GaussDB driver."""

from __future__ import annotations

import argparse
import importlib
import os
import sys
from pathlib import Path
from urllib.parse import parse_qsl
from urllib.parse import urlsplit
from urllib.parse import urlunsplit


def _mask_url(url: str) -> str:
    parts = urlsplit(url)
    if not parts.password:
        return url
    username = parts.username or ""
    host = parts.hostname or ""
    port = f":{parts.port}" if parts.port else ""
    netloc = f"{username}:***@{host}{port}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


def _check_import(module_name: str) -> object | None:
    try:
        module = importlib.import_module(module_name)
    except Exception as exc:
        print(f"[FAIL] import {module_name}: {type(exc).__name__}: {exc}")
        return None

    version = getattr(module, "__version__", "unknown")
    print(f"[ OK ] import {module_name}: {version}")
    return module


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check GaussDB Python and SQLAlchemy driver availability."
    )
    parser.add_argument(
        "--url",
        default=os.environ.get("GAUSSDB_TEST_URL"),
        help="Optional SQLAlchemy URL used for a live select 1 check.",
    )
    args = parser.parse_args()

    print(f"Python: {sys.version.split()[0]}")
    print(f"Executable: {sys.executable}")
    print(f"PATH: {os.environ.get('PATH', '')}")

    sqlalchemy = _check_import("sqlalchemy")
    dialect = _check_import("gaussdb_sqlalchemy")
    jaydebeapi = _check_import("jaydebeapi")
    jpype = _check_import("jpype")
    if args.url:
        query = dict(parse_qsl(urlsplit(args.url).query, keep_blank_values=True))
        jar = query.get("jdbc_driver_path")
        if jar:
            jar_path = Path(jar)
            if jar_path.exists():
                print(f"[ OK ] JDBC driver jar: {jar_path}")
            else:
                print(f"[FAIL] JDBC driver jar not found: {jar_path}")
                return 1

    if not all((sqlalchemy, dialect, jaydebeapi, jpype)):
        print()
        print("请确认已安装 JayDeBeApi、JPype1、SQLAlchemy 和本项目 wheel。")
        print("Windows 上还需要安装 Java Runtime，并提供 GaussDB JDBC jar。")
        return 1

    if not args.url:
        print("[SKIP] 未提供 --url 或 GAUSSDB_TEST_URL，跳过真实连接检查。")
        return 0

    from sqlalchemy import create_engine
    from sqlalchemy import text

    print(f"Connecting: {_mask_url(args.url)}")
    try:
        engine = create_engine(args.url, pool_pre_ping=True)
        with engine.connect() as conn:
            value = conn.execute(text("select 1")).scalar_one()
    except Exception as exc:
        print(f"[FAIL] live connection: {type(exc).__name__}: {exc}")
        return 2

    print(f"[ OK ] live connection: select 1 -> {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
