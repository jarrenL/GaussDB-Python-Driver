"""SQLAlchemy dialect using Huawei's ``gaussdb`` DB-API package."""

from __future__ import annotations

import re
from typing import Any

from . import dbapi as gaussdb_dbapi
from .alembic import register_alembic_impl
from .base import GaussDBDialect


register_alembic_impl()


class GaussDBDialect_gaussdb(GaussDBDialect):
    """GaussDB dialect backed by the Huawei ``gaussdb`` DB-API adapter."""

    driver = "gaussdb"
    supports_statement_cache = True

    @classmethod
    def import_dbapi(cls):
        return gaussdb_dbapi

    def create_connect_args(self, url):
        opts = url.translate_connect_args(username="user", database="dbname")
        opts.update(url.query)
        opts.setdefault("client_encoding", "UTF8")

        port = opts.get("port")
        if port is not None:
            opts["port"] = int(port)

        return [], opts

    def on_connect(self):
        hooks = []

        if self.isolation_level is not None:

            def set_isolation_level(conn):
                self.set_isolation_level(conn, self.isolation_level)

            hooks.append(set_isolation_level)

        def receive_notices(conn):
            add_notice_handler = getattr(conn, "add_notice_handler", None)
            if add_notice_handler is not None:
                add_notice_handler(self._log_notice)

        hooks.append(receive_notices)

        def on_connect(conn):
            for hook in hooks:
                hook(conn)

        return on_connect

    def is_disconnect(self, e: BaseException, connection: Any, cursor: Any) -> bool:
        if connection is not None:
            closed = getattr(connection, "closed", False)
            broken = getattr(connection, "broken", False)
            if closed or broken:
                return True

        message = str(e).lower()
        return bool(
            re.search(
                r"(connection.*closed|connection.*lost|server closed|"
                r"terminating connection|could not receive data)",
                message,
            )
        )

    @staticmethod
    def _log_notice(notice):
        # SQLAlchemy does not require notice logging; exposing a handler keeps
        # psycopg-compatible adapters from buffering server notices forever.
        return None


dialect = GaussDBDialect_gaussdb
