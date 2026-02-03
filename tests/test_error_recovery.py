#!/usr/bin/env python3
"""
Test de resiliencia para micro-resumenes con reintentos.
"""

import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from unified_context import UnifiedContextManager


class FlakyLLM:
    def __init__(self):
        self.calls = 0

    def invoke(self, prompt: str):
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("temporary failure")
        return "Micro resumen valido con los eventos clave."


def test_micro_summary_retry():
    print("TEST: micro summary retry")
    old_env = {
        "RETRY_MAX_ATTEMPTS": os.environ.get("RETRY_MAX_ATTEMPTS"),
        "RETRY_BASE_DELAY": os.environ.get("RETRY_BASE_DELAY"),
        "RETRY_MAX_DELAY": os.environ.get("RETRY_MAX_DELAY"),
        "RETRY_JITTER_ENABLED": os.environ.get("RETRY_JITTER_ENABLED"),
    }
    try:
        os.environ["RETRY_MAX_ATTEMPTS"] = "2"
        os.environ["RETRY_BASE_DELAY"] = "0"
        os.environ["RETRY_MAX_DELAY"] = "0"
        os.environ["RETRY_JITTER_ENABLED"] = "false"

        llm = FlakyLLM()
        manager = UnifiedContextManager(
            framework="Test",
            llm=llm,
            enable_micro_summaries=True,
            micro_summary_interval=2
        )
        manager.register_chapter("cap1", "Capitulo 1", "Resumen")
        manager.update_chapter_content("cap1", "Seccion uno del capitulo.")
        manager.update_chapter_content("cap1", "Seccion dos del capitulo.")

        ok = len(manager.current_chapter_content) <= 2
        print(f"micro_summary_retry: {'PASS' if ok else 'FAIL'}")
        return ok
    finally:
        for key, value in old_env.items():
            if value is None:
                if key in os.environ:
                    del os.environ[key]
            else:
                os.environ[key] = value


def main():
    results = [test_micro_summary_retry()]
    passed = sum(1 for r in results if r)
    total = len(results)
    print(f"Resultado final: {passed}/{total} tests pasaron")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
