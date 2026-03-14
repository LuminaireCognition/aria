"""Regression test: SCHEMA_SQL metadata version stays in sync with SCHEMA_VERSION."""

from aria_esi.store.market.database import SCHEMA_SQL, SCHEMA_VERSION


def test_schema_sql_version_matches_constant():
    """Ensure SCHEMA_SQL metadata version stays in sync with SCHEMA_VERSION."""
    formatted = SCHEMA_SQL.format(schema_version=SCHEMA_VERSION)
    assert f"'{SCHEMA_VERSION}'" in formatted
