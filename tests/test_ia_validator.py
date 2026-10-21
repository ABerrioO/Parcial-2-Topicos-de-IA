"""Pruebas del módulo de IA aplicada (PLN, similitud, semántica, anomalías)."""

from __future__ import annotations

import pandas as pd
import pytest

from modules.ia_validator import (
    analizar_duplicados,
    detectar_anomalias,
    detectar_duplicados,
    mapear_encabezados,
    normalizar_nombre,
    redactar_mensaje,
    validar_correo_ia,
)


# ── Caso 3: normalización de nombres con tildes ───────────────────────────
@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("María José Pérez", "Maria Jose Perez"),
        ("  juan   perez  ", "Juan Perez"),
        ("maria jose", "Maria Jose"),
        ("", ""),
        (None, ""),
        (float("nan"), ""),
    ],
)
def test_normalizar_nombre(entrada, esperado):
    assert normalizar_nombre(entrada) == esperado


def test_normalizar_particulas_en_minuscula():
    assert normalizar_nombre("juan de la cruz gómez") == "Juan de la Cruz Gomez"


def test_normalizar_conserva_enie_si_se_pide():
    assert normalizar_nombre("Muñoz", preservar_enie=True) == "Muñoz"


# ── Caso 4: validación de correo ──────────────────────────────────────────
@pytest.mark.parametrize(
    "correo",
    [
        "juan.perez@lasalle.edu.co",
        "nombre+evento@correo.com",
        "a_b-c@dominio.co",
    ],
)
def test_correos_validos(correo):
    assert validar_correo_ia(correo) is True


@pytest.mark.parametrize(
    "correo",
    [
        "juan@sinDominio",
        "juan.perez@",
        "@correo.com",
        "juan perez@correo.com",
        "juan@@correo.com",
        "juan@correo..com",
        "",
        None,
    ],
)
def test_correos_invalidos(correo):
    assert validar_correo_ia(correo) is False


# ── Caso 5: detección de duplicados por similitud ─────────────────────────
def test_detectar_duplicados_por_correo():
    df = pd.DataFrame(
        {
            "nombres": ["juan", "juan", "maria"],
            "apellidos": ["perez", "perez", "lopez"],
            "correo": [
                "juan.perez@uni.edu.co",
                "juan.perez@uni.edu.com",  # 95 % de similitud
                "maria.lopez@uni.edu.co",
            ],
        }
    )
    duplicados = detectar_duplicados(df, umbral=90)
    assert duplicados, "Debe detectar el par de correos similar"
    i, j, score = duplicados[0]
    assert (i, j) == (0, 1)
    assert score >= 90


def test_detectar_duplicados_no_reporta_distintos():
    df = pd.DataFrame(
        {
            "nombres": ["ana", "bob"],
            "apellidos": ["diaz", "diaz"],
            "correo": ["ana.diaz@correo.com", "bob.diaz@correo.com"],
        }
    )
    assert detectar_duplicados(df, umbral=90) == []


def test_analizar_duplicados_incluye_detalle():
    df = pd.DataFrame(
        {
            "nombres": ["juan", "juan"],
            "apellidos": ["perez", "perez"],
            "correo": ["juan.perez@uni.edu.co", "juan.perez@uni.edu.com"],
        }
    )
    hallazgos = analizar_duplicados(df)
    assert hallazgos
    assert hallazgos[0]["tipo"] == "correo"
    assert hallazgos[0]["similitud"] >= 90


# ── Caso 6: mapeo semántico de encabezados ────────────────────────────────
def test_mapear_encabezados_variantes():
    mapeo = mapear_encabezados(["Nombre Completo", "Email", "Cédula", "Nombres", "Apellidos"])
    assert mapeo["Nombre Completo"] == "nombres"
    assert mapeo["Email"] == "correo"
    assert mapeo["Cédula"] == "documento"
    assert mapeo["Nombres"] == "nombres"
    assert mapeo["Apellidos"] == "apellidos"


def test_mapear_encabezados_ignora_columnas_irrelevantes():
    mapeo = mapear_encabezados(["observaciones", "telefono"])
    assert mapeo == {}


# ── Detección de anomalías ────────────────────────────────────────────────
def test_detectar_anomalias_correo_invalido():
    anomalias = detectar_anomalias(
        {"nombres": "Juan", "apellidos": "Perez", "correo": "juan@sinDominio"}
    )
    assert any("formato válido" in a for a in anomalias)


def test_detectar_anomalias_nombre_vacio():
    anomalias = detectar_anomalias({"nombres": "", "apellidos": "Perez", "correo": "a@b.co"})
    assert any("nombres" in a for a in anomalias)


def test_detectar_anomalias_documento_atipico():
    anomalias = detectar_anomalias(
        {"nombres": "Juan", "apellidos": "Perez", "correo": "a@b.co", "documento": "1"}
    )
    assert any("longitud atípica" in a for a in anomalias)


def test_sin_anomalias_con_fila_completa():
    anomalias = detectar_anomalias(
        {
            "nombres": "Juan",
            "apellidos": "Perez",
            "correo": "juan@correo.com",
            "documento": "1010101010",
        }
    )
    assert anomalias == []


# ── Redacción asistida (IA generativa con respaldo local) ─────────────────
def test_redactar_mensaje_usa_plantilla():
    mensaje = redactar_mensaje("Juan Perez", "Ponente", "Congreso 2026", usar_llm=False)
    assert "Congreso 2026" in mensaje["cuerpo_html"]
    assert mensaje["origen"] == "plantilla institucional"
    assert "Congreso 2026" in mensaje["asunto"]
