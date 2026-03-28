"""
tests/conftest.py
==================
Shared pytest configuration and fixtures.
Automatically loaded by pytest before any test runs.
"""

import pytest
import sys
import os

# Add project root to Python path so imports work correctly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def pytest_configure(config):
    """Register custom pytest markers."""
    config.addinivalue_line(
        "markers",
        "integration: mark test as integration test (requires internet + trained models)"
    )


def pytest_addoption(parser):
    parser.addoption(
        "--integration",
        action="store_true",
        default=False,
        help="Run integration tests (requires internet and trained models)"
    )


def pytest_collection_modifyitems(config, items):
    """
    Auto-skip integration tests unless --integration flag is passed.
    Run all tests:        pytest
    Run integration too:  pytest --integration
    """
    if not config.getoption("--integration", default=False):
        skip_integration = pytest.mark.skip(
            reason="Integration test — run with: pytest --integration"
        )
        for item in items:
            if "integration" in item.keywords:
                item.add_marker(skip_integration)