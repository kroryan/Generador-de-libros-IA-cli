#!/usr/bin/env python3
"""
Test basico de configuracion centralizada, incluyendo SummaryConfig.
"""

import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from config.defaults import reload_config


def _set_env(key: str, value: str):
    if value is None:
        if key in os.environ:
            del os.environ[key]
    else:
        os.environ[key] = value


def test_summary_overrides():
    print("TEST: SummaryConfig overrides")
    old_values = {
        "SUMMARY_SAVEPOINT_MAX_CHARS": os.environ.get("SUMMARY_SAVEPOINT_MAX_CHARS"),
        "SUMMARY_SECTION_MIN_CHARS": os.environ.get("SUMMARY_SECTION_MIN_CHARS"),
        "CONTEXT_GLOBAL_LIMIT": os.environ.get("CONTEXT_GLOBAL_LIMIT"),
        "CONTEXT_MICRO_SUMMARY_INTERVAL": os.environ.get("CONTEXT_MICRO_SUMMARY_INTERVAL"),
    }

    try:
        _set_env("SUMMARY_SAVEPOINT_MAX_CHARS", "321")
        _set_env("SUMMARY_SECTION_MIN_CHARS", "77")
        _set_env("CONTEXT_GLOBAL_LIMIT", "1234")
        _set_env("CONTEXT_MICRO_SUMMARY_INTERVAL", "4")

        config = reload_config()

        checks = [
            config.summary.savepoint_summary_max_chars == 321,
            config.summary.section_min_chars == 77,
            config.context.global_context_size == 1234,
            config.context.micro_summary_interval == 4
        ]

        ok = all(checks)
        print(f"summary_overrides: {'PASS' if ok else 'FAIL'}")
        return ok
    finally:
        for key, value in old_values.items():
            _set_env(key, value)
        reload_config()


def main():
    results = [test_summary_overrides()]
    passed = sum(1 for r in results if r)
    total = len(results)
    print(f"Resultado final: {passed}/{total} tests pasaron")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
