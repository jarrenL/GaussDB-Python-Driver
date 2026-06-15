from gaussdb_sqlalchemy.base import GaussDBDialect


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
