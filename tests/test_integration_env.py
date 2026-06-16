import os
import uuid

import pytest
from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import MetaData
from sqlalchemy import String
from sqlalchemy import Table
from sqlalchemy import create_engine
from sqlalchemy import inspect
from sqlalchemy import select
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.orm import declarative_base


def _test_url():
    url = os.environ.get("GAUSSDB_TEST_URL")
    if not url:
        pytest.skip("GAUSSDB_TEST_URL is not configured")
    return url


def _engine(**kwargs):
    return create_engine(_test_url(), pool_pre_ping=True, **kwargs)


def _table_name(prefix):
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _drop_table(conn, table_name):
    conn.execute(text(f"drop table if exists {table_name}"))


@pytest.mark.integration
def test_sqlalchemy_core_roundtrip_against_gaussdb_url_from_env():
    engine = _engine()
    table_name = _table_name("codex_core_ut")

    with engine.begin() as conn:
        _drop_table(conn, table_name)
        conn.execute(
            text(f"create table {table_name} (id int primary key, name varchar(32))")
        )
        conn.execute(
            text(f"insert into {table_name} (id, name) values (:id, :name)"),
            {"id": 1, "name": "ok"},
        )
        row = conn.execute(
            text(f"select id, name from {table_name} where id=:id"),
            {"id": 1},
        ).one()
        assert row == (1, "ok")
        _drop_table(conn, table_name)


@pytest.mark.integration
def test_transaction_rollback_against_gaussdb_url_from_env():
    engine = _engine()
    table_name = _table_name("codex_tx_ut")

    with engine.begin() as conn:
        _drop_table(conn, table_name)
        conn.execute(
            text(f"create table {table_name} (id int primary key, name varchar(32))")
        )

    try:
        with engine.connect() as conn:
            trans = conn.begin()
            conn.execute(
                text(f"insert into {table_name} (id, name) values (:id, :name)"),
                {"id": 1, "name": "rollback"},
            )
            trans.rollback()

        with engine.begin() as conn:
            count = conn.execute(text(f"select count(*) from {table_name}")).scalar_one()
            assert count == 0
    finally:
        with engine.begin() as conn:
            _drop_table(conn, table_name)


@pytest.mark.integration
def test_bulk_insert_against_gaussdb_url_from_env():
    engine = _engine()
    table_name = _table_name("codex_bulk_ut")

    with engine.begin() as conn:
        _drop_table(conn, table_name)
        conn.execute(
            text(f"create table {table_name} (id int primary key, name varchar(32))")
        )
        conn.execute(
            text(f"insert into {table_name} (id, name) values (:id, :name)"),
            [{"id": idx, "name": f"name-{idx}"} for idx in range(1, 6)],
        )
        count = conn.execute(text(f"select count(*) from {table_name}")).scalar_one()
        assert count == 5
        _drop_table(conn, table_name)


@pytest.mark.integration
def test_orm_crud_against_gaussdb_url_from_env():
    engine = _engine()
    table_name = _table_name("codex_orm_ut")
    Base = declarative_base()

    class DriverUser(Base):
        __tablename__ = table_name

        id = Column(Integer, primary_key=True)
        name = Column(String(32), nullable=False)

    try:
        Base.metadata.create_all(engine)

        with Session(engine) as session:
            session.add(DriverUser(id=1, name="created"))
            session.commit()

        with Session(engine) as session:
            user = session.get(DriverUser, 1)
            assert user is not None
            assert user.name == "created"
            user.name = "updated"
            session.commit()

        with Session(engine) as session:
            assert session.scalar(select(DriverUser.name).where(DriverUser.id == 1)) == (
                "updated"
            )
            session.delete(session.get(DriverUser, 1))
            session.commit()

        with Session(engine) as session:
            assert session.get(DriverUser, 1) is None
    finally:
        Base.metadata.drop_all(engine)


@pytest.mark.integration
def test_metadata_reflection_against_gaussdb_url_from_env():
    engine = _engine()
    table_name = _table_name("codex_reflect_ut")
    metadata = MetaData()
    table = Table(
        table_name,
        metadata,
        Column("id", Integer, primary_key=True),
        Column("name", String(32), nullable=False),
    )

    try:
        metadata.create_all(engine)

        reflected = MetaData()
        reflected_table = Table(table_name, reflected, autoload_with=engine)
        assert reflected_table.c.id.primary_key
        assert reflected_table.c.name.nullable is False

        inspector = inspect(engine)
        columns = {column["name"]: column for column in inspector.get_columns(table_name)}
        assert set(columns) == {"id", "name"}
        assert columns["id"]["nullable"] is False
        assert columns["name"]["nullable"] is False
    finally:
        metadata.drop_all(engine)


@pytest.mark.integration
def test_connection_pool_reuses_connectable_against_gaussdb_url_from_env():
    engine = _engine(pool_size=1, max_overflow=0)

    for _ in range(3):
        with engine.connect() as conn:
            assert conn.execute(text("select 1")).scalar_one() == 1

    assert "Pool size: 1" in engine.pool.status()
