"""Run a live GaussDB SQLAlchemy integration probe.

The script expects GAUSSDB_TEST_URL or --url and creates temporary tables with
``codex_*`` prefixes. It is intentionally framework-free so it can run on a
database host even when pytest is not installed.
"""

from __future__ import annotations

import argparse
import os
import uuid

from sqlalchemy import Column
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import MetaData
from sqlalchemy import String
from sqlalchemy import Table
from sqlalchemy import UniqueConstraint
from sqlalchemy import create_engine
from sqlalchemy import inspect
from sqlalchemy import text


def table_name(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def run(url: str) -> tuple[str, ...]:
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    engine = create_engine(url, pool_pre_ping=True)
    results: tuple[str, ...] = ()

    table = table_name("codex_idx_ut")
    index_name = f"ix_{table}_name"
    unique_name = f"uq_{table}_code"
    metadata = MetaData()
    Table(
        table,
        metadata,
        Column("id", Integer, primary_key=True),
        Column("code", String(32), nullable=False),
        Column("name", String(32), nullable=False),
        UniqueConstraint("code", name=unique_name),
        Index(index_name, "name"),
    )
    try:
        metadata.create_all(engine)
        inspector = inspect(engine)
        pk = inspector.get_pk_constraint(table)
        assert_true(pk["constrained_columns"] == ["id"], f"unexpected pk: {pk}")

        uniques = inspector.get_unique_constraints(table)
        assert_true(
            any(
                constraint["name"] == unique_name
                and constraint["column_names"] == ["code"]
                for constraint in uniques
            ),
            f"unexpected unique constraints: {uniques}",
        )

        indexes = inspector.get_indexes(table)
        assert_true(
            any(
                index["name"] == index_name and index["column_names"] == ["name"]
                for index in indexes
            ),
            f"unexpected indexes: {indexes}",
        )
    finally:
        metadata.drop_all(engine)
    results += ("pk_unique_index",)

    table = table_name("codex_seq_ut")
    sequence = f"{table}_id_seq"
    with engine.begin() as conn:
        conn.execute(text(f"drop table if exists {table}"))
        conn.execute(text(f"drop sequence if exists {sequence}"))
        conn.execute(text(f"create sequence {sequence} start 1"))
        conn.execute(
            text(
                f"create table {table} ("
                f"id int primary key default nextval('{sequence}'), "
                "name varchar(32))"
            )
        )
        conn.execute(text(f"insert into {table} (name) values (:name)"), {"name": "a"})
        conn.execute(text(f"insert into {table} (name) values (:name)"), {"name": "b"})
        rows = conn.execute(text(f"select id, name from {table} order by id")).all()
        assert_true(rows == [(1, "a"), (2, "b")], f"unexpected rows: {rows}")

        columns = {column["name"]: column for column in inspect(conn).get_columns(table)}
        assert_true(
            "nextval" in columns["id"]["default"],
            f"unexpected default: {columns['id']}",
        )
        conn.execute(text(f"drop table {table}"))
        conn.execute(text(f"drop sequence {sequence}"))
    results += ("sequence",)

    table = table_name("codex_alembic_ut")
    with engine.begin() as conn:
        context = MigrationContext.configure(conn)
        operations = Operations(context)
        operations.create_table(
            table,
            Column("id", Integer, primary_key=True),
            Column("name", String(32), nullable=False),
        )
        operations.add_column(table, Column("remark", String(64)))
        conn.execute(
            text(
                f"insert into {table} (id, name, remark) "
                "values (:id, :name, :remark)"
            ),
            {"id": 1, "name": "created", "remark": "via alembic"},
        )
        row = conn.execute(
            text(f"select id, name, remark from {table} where id=:id"),
            {"id": 1},
        ).one()
        assert_true(
            row == (1, "created", "via alembic"),
            f"unexpected alembic row: {row}",
        )
        operations.drop_table(table)
    results += ("alembic",)

    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=os.environ.get("GAUSSDB_TEST_URL"))
    args = parser.parse_args()
    if not args.url:
        parser.error("--url or GAUSSDB_TEST_URL is required")

    results = run(args.url)
    print("integration probe ok:", ",".join(results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
