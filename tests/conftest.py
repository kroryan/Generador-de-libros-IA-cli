"""Pytest compatibility for the project's legacy executable test scripts."""

from pathlib import Path
import sys

import pytest


SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

collect_ignore = [
    "test_app_params.py",
    "test_chain_debug.py",
    "test_debug_discovery.py",
    "test_discovery.py",
    "test_env_vars.py",
    "test_exact_app.py",
    "test_ollama_client.py",
    "test_ollama_direct.py",
    "test_ollama_handler.py",
    "test_parse_model.py",
    "test_provider_chain.py",
    "test_simple.py",
]


@pytest.hookimpl(tryfirst=True)
def pytest_pyfunc_call(pyfuncitem):
    """Treat legacy boolean test results as assertions instead of ignoring them."""
    test_args = {
        name: pyfuncitem.funcargs[name]
        for name in pyfuncitem._fixtureinfo.argnames
    }
    result = pyfuncitem.obj(**test_args)
    if isinstance(result, bool):
        assert result, f"{pyfuncitem.nodeid} returned False"
    elif result is not None:
        pytest.fail(
            f"{pyfuncitem.nodeid} returned unsupported value {result!r}",
            pytrace=False,
        )
    return True
