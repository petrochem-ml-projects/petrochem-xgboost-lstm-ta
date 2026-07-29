"""Sanity check that CI's Postgres-via-testcontainers wiring actually works.
This module exists purely to give the `integration` pytest marker a real
test to run ahead of Phase 1's domain code (`PostgresDataSink`,
`PostgresProcessDataRepository`) landing. It intentionally exercises no
application logic — there is none to test yet.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text
from testcontainers.postgres import PostgresContainer

pytestmark = pytest.mark.integration


def test_postgres_container_roundtrip() -> None:
    """A Postgres testcontainer starts, accepts a connection and answers SELECT 1"""
    with PostgresContainer("postgres:16") as postgres:
        engine = create_engine(postgres.get_connection_url())
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1")).scalar_one()
    assert result == 1
