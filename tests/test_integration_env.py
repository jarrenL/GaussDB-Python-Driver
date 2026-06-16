import os

import pytest
from sqlalchemy import create_engine, text


@pytest.mark.integration
def test_sqlalchemy_roundtrip_against_gaussdb_url_from_env():
    url = os.environ.get("GAUSSDB_TEST_URL")
    if not url:
        pytest.skip("GAUSSDB_TEST_URL is not configured")

    engine = create_engine(url, pool_pre_ping=True)
    table_name = "codex_sqlalchemy_env_ut"

    with engine.begin() as conn:
        assert conn.execute(text("select 1")).scalar_one() == 1
        conn.execute(text(f"drop table if exists {table_name}"))
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
        conn.execute(text(f"drop table {table_name}"))
