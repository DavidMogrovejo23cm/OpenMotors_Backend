"""Ejecutar pytest; --sandbox-polling permite pruebas ASGI sin socket de aviso.

Uso normal: .venv/bin/python scripts/run_tests.py -q
Entorno restringido: .venv/bin/python scripts/run_tests.py --sandbox-polling -q
El modo polling solo cambia la espera del selector; no simula las respuestas API.
"""
import os
from pathlib import Path
import sys

os.chdir(Path(__file__).resolve().parents[1])
sys.path.insert(0, str(Path.cwd()))
if "--sandbox-polling" in sys.argv:
    import selectors
    sys.argv.remove("--sandbox-polling")
    _original_select = selectors.DefaultSelector.select

    def _polling_select(self, timeout=None):
        return _original_select(self, 0.01 if timeout is None else min(timeout, 0.01))

    selectors.DefaultSelector.select = _polling_select

import pytest

raise SystemExit(pytest.main(sys.argv[1:]))
