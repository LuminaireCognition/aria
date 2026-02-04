"""
Benchmark Suite Fixtures

Provides fixtures for performance benchmarks using pytest-benchmark.

STP-012: Testing & Deployment
"""

import pytest


@pytest.fixture(scope="session")
def benchmark_universe(real_universe):
    """
    Universe graph for benchmarks.

    Requires real universe.pkl to be built.
    Skips benchmark if not available.
    """
    return real_universe
