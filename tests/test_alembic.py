import pytest

from gaussdb_sqlalchemy.alembic import register_alembic_impl


def test_register_alembic_impl_when_alembic_is_installed():
    pytest.importorskip("alembic")
    from alembic.ddl.impl import _impls

    assert register_alembic_impl() is True
    registered_impl = _impls["gaussdb"]
    assert register_alembic_impl() is True
    assert _impls["gaussdb"] is registered_impl
    assert _impls["gaussdb"].__dialect__ == "gaussdb"
