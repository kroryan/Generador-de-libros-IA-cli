#!/usr/bin/env python3
"""
Test basico del sistema de savepoints con LLM stub.
"""

import os
import sys

# Anadir src al path para imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from writing import create_savepoint_summary


class StubLLM:
    def __init__(self, mode="ok"):
        self.mode = mode

    def invoke(self, prompt: str):
        if self.mode == "fail_primary" and "Resumen actualizado" in prompt:
            raise RuntimeError("LLM primary failure")
        return "Resumen de emergencia con detalles clave para continuar la historia."


def test_basic_savepoint():
    llm = StubLLM(mode="ok")
    summary = create_savepoint_summary(
        llm=llm,
        title="Libro Test",
        chapter_num=1,
        chapter_title="Capitulo Uno",
        current_summary="Inicio del capitulo 1",
        new_section="Contenido nuevo para resumir."
    )
    ok = isinstance(summary, str) and len(summary.strip()) > 0
    print(f"basic_savepoint: {'PASS' if ok else 'FAIL'}")
    return ok


def test_fallback_savepoint():
    llm = StubLLM(mode="fail_primary")
    summary = create_savepoint_summary(
        llm=llm,
        title="Libro Test",
        chapter_num=2,
        chapter_title="Capitulo Dos",
        current_summary="Resumen previo",
        new_section="Contenido nuevo para resumir con fallo primario."
    )
    ok = isinstance(summary, str) and len(summary.strip()) > 0
    print(f"fallback_savepoint: {'PASS' if ok else 'FAIL'}")
    return ok


def main():
    print("== TEST SAVEPOINT INTEGRATION ==")
    results = [
        test_basic_savepoint(),
        test_fallback_savepoint()
    ]
    passed = sum(1 for r in results if r)
    total = len(results)
    print(f"Resultado final: {passed}/{total} tests pasaron")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
