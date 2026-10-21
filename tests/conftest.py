"""Configuración compartida de las pruebas (fixtures de pytest)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from config import APP_CONFIG, SMTP_CONFIG  # noqa: E402
from modules import tracker  # noqa: E402


@pytest.fixture()
def entorno_temporal(tmp_path, monkeypatch):
    """Aísla base de datos, carpeta de salida y SMTP simulado."""
    base = tmp_path / "certificados_test.db"
    salida = tmp_path / "out"
    temporal = tmp_path / "tmp"
    salida.mkdir()
    temporal.mkdir()

    monkeypatch.setattr(tracker, "ruta_db", lambda: base)
    object.__setattr__(APP_CONFIG, "dir_salida", salida)
    object.__setattr__(APP_CONFIG, "dir_temporal", temporal)
    object.__setattr__(SMTP_CONFIG, "modo_simulacion", True)

    tracker.inicializar_db()
    yield tmp_path


@pytest.fixture()
def cliente(entorno_temporal):
    """Cliente de pruebas de la aplicación Flask."""
    import app as modulo_app

    modulo_app.app.config.update(TESTING=True)
    with modulo_app.app.test_client() as cliente:
        yield cliente


@pytest.fixture()
def libro_completo(tmp_path):
    """Genera un libro Excel válido con las cinco hojas requeridas."""
    import pandas as pd

    ruta = tmp_path / "evento.xlsx"
    with pd.ExcelWriter(ruta, engine="openpyxl") as escritor:
        pd.DataFrame(
            {
                "nombres": ["maria jose", "juan"],
                "apellidos": ["pérez", "quintero"],
                "correo": ["maria.perez@correo.com", "juan.quintero@correo.com"],
            }
        ).to_excel(escritor, sheet_name="Asistentes", index=False)

        pd.DataFrame(
            {
                "nombres": ["camila"],
                "apellidos": ["ruiz"],
                "correo": ["camila.ruiz@correo.com"],
                "documento": ["1010101010"],
                "ponencia": ["PLN aplicado a la educación"],
            }
        ).to_excel(escritor, sheet_name="Ponentes", index=False)

        pd.DataFrame(
            {
                "nombres": ["ricardo"],
                "apellidos": ["alvarez"],
                "correo": ["ricardo.alvarez@correo.com"],
                "documento": ["2020202020"],
                "conferencia": ["Ética de la IA"],
            }
        ).to_excel(escritor, sheet_name="Conferenciantes", index=False)

        pd.DataFrame(
            {
                "nombres": ["laura"],
                "apellidos": ["mendoza"],
                "correo": ["laura.mendoza@correo.com"],
                "documento": ["3030303030"],
            }
        ).to_excel(escritor, sheet_name="Evaluadores", index=False)

        pd.DataFrame(
            {
                "nombres": ["gabriela"],
                "apellidos": ["navarro"],
                "correo": ["gabriela.navarro@correo.com"],
            }
        ).to_excel(escritor, sheet_name="Organizadores", index=False)

    return ruta


@pytest.fixture()
def libro_incompleto(tmp_path):
    """Genera un libro Excel al que le faltan hojas requeridas."""
    import pandas as pd

    ruta = tmp_path / "incompleto.xlsx"
    with pd.ExcelWriter(ruta, engine="openpyxl") as escritor:
        pd.DataFrame(
            {"nombres": ["ana"], "apellidos": ["lopez"], "correo": ["ana@correo.com"]}
        ).to_excel(escritor, sheet_name="Asistentes", index=False)
        pd.DataFrame(
            {"nombres": ["pedro"], "apellidos": ["suarez"], "correo": ["pedro@correo.com"]}
        ).to_excel(escritor, sheet_name="Organizadores", index=False)

    return ruta
