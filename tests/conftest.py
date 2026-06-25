"""Pytest fixtures. The API/integration tests require a running Postgres+Redis
(use docker-compose). The unit tests for resolver/renderer/MAC logic run with
no external services."""
import os
import pytest

REQUIRES_STACK = pytest.mark.skipif(
    os.getenv("POLYPROV_TEST_STACK") != "1",
    reason="set POLYPROV_TEST_STACK=1 with docker-compose up to run integration tests",
)
