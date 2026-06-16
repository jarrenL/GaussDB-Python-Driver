from gaussdb_sqlalchemy.base import GaussDBDialect


class _ScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar(self):
        return self.value


class _Connection:
    def __init__(self, values):
        self.values = values

    def exec_driver_sql(self, statement):
        return _ScalarResult(self.values[statement])


def test_dialect_identity_and_defaults():
    assert GaussDBDialect.name == "gaussdb"
    assert GaussDBDialect.default_paramstyle == "pyformat"
    assert GaussDBDialect.supports_statement_cache is True
    assert GaussDBDialect.use_native_hstore is False


def test_normalize_gaussdb_version_keeps_integer_tuples():
    assert GaussDBDialect._normalize_gaussdb_version((5, 0, 5, 1)) == (5, 0, 5, 1)


def test_normalize_gaussdb_version_strips_non_numeric_suffixes():
    assert GaussDBDialect._normalize_gaussdb_version((5, "0.5", "505.1", "build")) == (
        5,
        0,
        505,
    )


def test_normalize_gaussdb_version_handles_empty_or_unknown_values():
    assert GaussDBDialect._normalize_gaussdb_version(None) is None
    assert GaussDBDialect._normalize_gaussdb_version(()) == ()
    assert GaussDBDialect._normalize_gaussdb_version(("GaussDB",)) == ("GaussDB",)


def test_get_server_version_info_supports_gaussdb_kernel_string():
    dialect = GaussDBDialect()
    connection = _Connection(
        {
            "select pg_catalog.version()": (
                b"gaussdb (GaussDB Kernel 507.0.0 build 1268bd4d) release"
            )
        }
    )

    assert dialect._get_server_version_info(connection) == (507, 0, 0)


def test_get_server_version_info_supports_postgresql_compatible_string():
    dialect = GaussDBDialect()
    connection = _Connection({"select pg_catalog.version()": "PostgreSQL 9.2.4"})

    assert dialect._get_server_version_info(connection) == (9, 2, 4)


def test_get_server_version_info_rejects_unknown_version_format():
    dialect = GaussDBDialect()
    connection = _Connection({"select pg_catalog.version()": "unknown database"})

    try:
        dialect._get_server_version_info(connection)
    except AssertionError as exc:
        assert "Could not determine GaussDB version" in str(exc)
    else:
        raise AssertionError("expected unknown version format to fail")


def test_get_default_schema_name_decodes_bytes():
    dialect = GaussDBDialect()
    connection = _Connection({"select current_schema()": b"public"})

    assert dialect._get_default_schema_name(connection) == "public"
