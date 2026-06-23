import os
import uuid

import pytest
from sqlalchemy import Column
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import MetaData
from sqlalchemy import String
from sqlalchemy import Table
from sqlalchemy import create_engine
from sqlalchemy import func
from sqlalchemy import inspect
from sqlalchemy import text


def _configured_urls():
    urls = []
    for env_name in (
        "GAUSSDB_TEST_URL",
        "GAUSSDB_TEST_URL_A",
        "GAUSSDB_TEST_URL_B",
        "GAUSSDB_TEST_URL_M",
    ):
        url = os.environ.get(env_name)
        if url:
            urls.append(pytest.param(env_name, url, id=env_name))

    for index, url in enumerate(filter(None, os.environ.get("GAUSSDB_TEST_URLS", "").split(","))):
        urls.append(pytest.param(f"GAUSSDB_TEST_URLS[{index}]", url.strip(), id=f"GAUSSDB_TEST_URLS_{index}"))

    if not urls:
        urls.append(pytest.param(None, None, id="no-gaussdb-url"))
    return urls


def _engine(url):
    if not url:
        pytest.skip(
            "Configure GAUSSDB_TEST_URL, GAUSSDB_TEST_URL_A/B/M, or "
            "GAUSSDB_TEST_URLS to run live GaussDB compatibility scenarios"
        )
    return create_engine(url, pool_pre_ping=True)


def _table_name(prefix):
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _compatibility(conn):
    return conn.execute(
        text(
            """
            select datcompatibility
            from pg_database
            where datname = current_database()
            """
        )
    ).scalar_one()


def _fetch_first(conn, sql):
    return conn.execute(text(sql)).fetchmany(3)


def _assert_pass(conn, sql):
    _fetch_first(conn, sql)


def _assert_fail(conn, sql):
    with pytest.raises(Exception):
        _fetch_first(conn, sql)
    conn.rollback()


def _exec_scalar(engine, sql):
    with engine.begin() as conn:
        return conn.execute(text(sql)).scalar_one()


def _exec_all(engine, statements):
    with engine.begin() as conn:
        result = None
        for sql in statements:
            cursor = conn.execute(text(sql))
            if sql.lstrip().lower().startswith("select"):
                result = cursor.fetchall()
        return result


def _expect_statement_failure(engine, sql):
    with pytest.raises(Exception):
        with engine.begin() as conn:
            conn.execute(text(sql))


@pytest.mark.integration
@pytest.mark.parametrize(("env_name", "url"), _configured_urls())
def test_live_connection_and_compatibility_probe(env_name, url):
    engine = _engine(url)

    with engine.connect() as conn:
        assert conn.execute(text("select 1")).scalar_one() == 1
        compatibility = _compatibility(conn)

    assert compatibility in {"A", "B", "M", "PG", "pg"}


@pytest.mark.integration
@pytest.mark.parametrize(("env_name", "url"), _configured_urls())
def test_postgresql_style_basic_sql_by_compatibility(env_name, url):
    engine = _engine(url)

    with engine.connect() as conn:
        compatibility = _compatibility(conn)
        _assert_pass(conn, "select '42'::int as value")
        _assert_pass(conn, "select now() is not null as ok")
        _assert_pass(conn, "select generate_series(1,3) as n limit 2")


@pytest.mark.integration
@pytest.mark.parametrize(("env_name", "url"), _configured_urls())
def test_oracle_style_sql_by_compatibility(env_name, url):
    engine = _engine(url)

    with engine.connect() as conn:
        compatibility = _compatibility(conn)
        _assert_pass(conn, "select 1 from dual")

        if compatibility == "M":
            _assert_fail(conn, "select nvl(null, 'fallback')")
            _assert_fail(conn, "select sysdate")
            _assert_fail(conn, "select rownum from pg_class limit 1")
        else:
            _assert_pass(conn, "select nvl(null, 'fallback')")
            _assert_pass(conn, "select sysdate from dual")
            _assert_pass(conn, "select rownum from pg_class limit 1")


@pytest.mark.integration
@pytest.mark.parametrize(("env_name", "url"), _configured_urls())
def test_mysql_style_sql_by_compatibility(env_name, url):
    engine = _engine(url)

    with engine.connect() as conn:
        compatibility = _compatibility(conn)
        _assert_pass(conn, "select concat('a', 'b') as value")

        if compatibility == "A":
            _assert_fail(conn, "select 1 as `value`")
            _assert_fail(conn, "select ifnull(null, 'fallback')")
            _assert_fail(conn, "select current_timestamp()")
        elif compatibility == "B":
            _assert_pass(conn, "select 1 as `value`")
            _assert_pass(conn, "select ifnull(null, 'fallback')")
            _assert_fail(conn, "select current_timestamp()")
        elif compatibility == "M":
            _assert_pass(conn, "select 1 as `value`")
            _assert_pass(conn, "select ifnull(null, 'fallback')")
            _assert_pass(conn, "select current_timestamp()")


@pytest.mark.integration
@pytest.mark.parametrize(("env_name", "url"), _configured_urls())
def test_auto_increment_and_sequence_syntax_by_compatibility(env_name, url):
    engine = _engine(url)
    serial_table = _table_name("gdbdrv_serial_case")
    auto_table = _table_name("gdbdrv_auto_case")
    sequence = _table_name("gdbdrv_seq_case")

    with engine.connect() as conn:
        compatibility = _compatibility(conn)

    try:
        if compatibility == "M":
            rows = _exec_all(
                engine,
                [
                    f"create table {auto_table} "
                    "(id int auto_increment primary key, name varchar(20))",
                    f"insert into {auto_table} (name) values ('ok')",
                    f"select id, name from {auto_table}",
                ],
            )
            assert rows == [(1, "ok")]

            _expect_statement_failure(
                engine,
                f"create table {serial_table} (id serial primary key, name varchar(20))",
            )
            _exec_all(engine, [f"create sequence {sequence} start 1"])
            assert _exec_scalar(engine, f"select nextval('{sequence}')") == 1
            _expect_statement_failure(
                engine,
                f"create table {serial_table} ("
                f"id int primary key default nextval('{sequence}'), name varchar(20))",
            )
        else:
            rows = _exec_all(
                engine,
                [
                    f"create table {serial_table} "
                    "(id serial primary key, name varchar(20))",
                    f"insert into {serial_table} (name) values ('ok')",
                    f"select id, name from {serial_table}",
                ],
            )
            assert rows == [(1, "ok")]

            auto_sql = (
                f"create table {auto_table} "
                "(id int auto_increment primary key, name varchar(20))"
            )
            if compatibility == "A":
                _expect_statement_failure(engine, auto_sql)
            elif compatibility == "B":
                _exec_all(engine, [auto_sql])
    finally:
        with engine.begin() as conn:
            conn.execute(text(f"drop table if exists {serial_table}"))
            conn.execute(text(f"drop table if exists {auto_table}"))
            conn.execute(text(f"drop sequence if exists {sequence}"))


@pytest.mark.integration
@pytest.mark.parametrize(("env_name", "url"), _configured_urls())
def test_sqlalchemy_expression_index_by_compatibility(env_name, url):
    engine = _engine(url)
    table_name = _table_name("gdbdrv_expr_case")
    index_name = f"ix_{table_name}_lower_name"
    metadata = MetaData()
    table = Table(
        table_name,
        metadata,
        Column("id", Integer, primary_key=True),
        Column("name", String(32)),
    )
    Index(index_name, func.lower(table.c.name))

    try:
        metadata.create_all(engine)
        indexes = {index["name"] for index in inspect(engine).get_indexes(table_name)}
        assert index_name in indexes
    finally:
        metadata.drop_all(engine)
