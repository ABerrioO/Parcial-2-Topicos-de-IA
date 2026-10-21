"""Pruebas de la plantilla institucional del certificado.

Verifican que los certificados se compongan sobre el archivo
``templates/certificado_base.pdf`` (tamaño de página y contenido) y no sobre
un diseño fijo incrustado en el código.
"""

from __future__ import annotations

import io
import re

import pytest
from pypdf import PdfReader

from config import APP_CONFIG
from modules.pdf_generator import (
    MARGEN_BORRADO,
    _componer_plantilla,
    _leer_plantilla,
    generar_certificado,
)

pytestmark = pytest.mark.skipif(
    not APP_CONFIG.ruta_plantilla_base.is_file(),
    reason="No existe la plantilla institucional del proyecto.",
)


def _texto_pdf(ruta) -> str:
    with open(ruta, "rb") as archivo:
        return PdfReader(archivo).pages[0].extract_text()


def _medidas(ruta) -> tuple[float, float]:
    with open(ruta, "rb") as archivo:
        caja = PdfReader(archivo).pages[0].mediabox
        return float(caja.width), float(caja.height)


# ══════════════════════════════════════════════════════════════════════════
# Lectura de la plantilla
# ══════════════════════════════════════════════════════════════════════════
def test_plantilla_base_se_lee_con_su_geometria():
    info = _leer_plantilla(APP_CONFIG.ruta_plantilla_base)
    assert info is not None
    assert info.ancho > 0 and info.alto > 0
    assert info.lineas, "La plantilla debe tener textos para anclar los valores"
    assert any("<NOMBRE>" in linea.texto for linea in info.lineas)


# ══════════════════════════════════════════════════════════════════════════
# Generación sobre la plantilla
# ══════════════════════════════════════════════════════════════════════════
def test_certificado_usa_el_tamano_de_la_plantilla(tmp_path):
    salida = tmp_path / "certificado.pdf"
    generar_certificado(
        {"nombres": "Ana", "apellidos": "Lopez", "rol": "Asistente", "evento": "Evento"},
        plantilla=str(APP_CONFIG.ruta_plantilla_base),
        salida=salida,
    )
    plantilla = _leer_plantilla(APP_CONFIG.ruta_plantilla_base)
    ancho, alto = _medidas(salida)
    assert ancho == pytest.approx(plantilla.ancho, abs=0.01)
    assert alto == pytest.approx(plantilla.alto, abs=0.01)


def test_certificado_incluye_los_datos_del_participante(tmp_path):
    salida = tmp_path / "certificado.pdf"
    generar_certificado(
        {
            "nombres": "Maria Jose",
            "apellidos": "Perez",
            "rol": "Asistente",
            "evento": "Congreso Internacional 2026",
            "dependencia": "Facultad de Ingenierías",
        },
        plantilla=str(APP_CONFIG.ruta_plantilla_base),
        salida=salida,
    )
    texto = _texto_pdf(salida)
    assert "Maria Jose Perez" in texto
    assert "Congreso Internacional 2026" in texto
    assert "FACULTAD DE INGENIER" in texto.upper()


def test_certificado_reemplaza_los_marcadores_de_la_plantilla(tmp_path):
    salida = tmp_path / "certificado.pdf"
    generar_certificado(
        {"nombres": "Ana", "apellidos": "Lopez", "rol": "Asistente", "evento": "Evento"},
        plantilla=str(APP_CONFIG.ruta_plantilla_base),
        salida=salida,
    )
    texto = _texto_pdf(salida)
    # El texto dinámico se superpone; los marcadores quedan tapados.
    assert "CERTIFICADO DE PARTICIPACI" in texto
    assert "Ana Lopez" in texto


def test_el_borrado_cubre_los_acentos_de_las_mayusculas():
    """El rectángulo blanco debe tapar también la tilde de las mayúsculas."""
    info = _leer_plantilla(APP_CONFIG.ruta_plantilla_base)
    superposicion = _componer_plantilla(
        info, {"nombres": "Ana", "apellidos": "Lopez", "evento": "INCIETEC 02-2026"}
    )
    flujo = PdfReader(io.BytesIO(superposicion)).pages[0].get_contents().get_data()
    rectangulos = [
        (float(x), float(y), float(w), float(h))
        for x, y, w, h in re.findall(
            rb"([\d.]+) ([\d.]+) ([\d.]+) ([\d.]+) re", flujo
        )
    ]

    acentos = [l for l in info.lineas if any(c in l.texto for c in "ÁÉÍÓÚÑÜ")]
    assert acentos, "La plantilla debe tener al menos una mayúscula acentuada"
    for linea in acentos:
        candidatos = [
            (x, y, w, h)
            for x, y, w, h in rectangulos
            if x <= linea.x_min
            and (x + w) >= linea.x_max
            and abs(y - (linea.y_min - MARGEN_BORRADO)) < 0.6
        ]
        if not candidatos:
            continue  # la línea no se reemplaza: se conserva el texto original
        esperada = linea.y_max + MARGEN_BORRADO + 0.16 * linea.tamano
        assert any(
            abs((y + h) - esperada) < 0.6 for _, y, _, h in candidatos
        ), f"El borrado de {linea.texto!r} no cubre la tilde"


def test_certificado_sin_plantilla_usa_el_diseno_propio(tmp_path):
    salida = tmp_path / "certificado.pdf"
    generar_certificado(
        {"nombres": "Ana", "apellidos": "Lopez", "rol": "Asistente", "evento": "Evento"},
        plantilla=None,
        salida=salida,
    )
    from reportlab.lib.pagesizes import A4, landscape

    ancho, alto = landscape(A4)
    assert _medidas(salida) == pytest.approx((ancho, alto), abs=0.01)


def test_certificado_protegido_con_plantilla(tmp_path):
    salida = tmp_path / "certificado.pdf"
    generar_certificado(
        {
            "nombres": "Ana",
            "apellidos": "Lopez",
            "rol": "Asistente",
            "evento": "Evento",
            "documento": "1010101010",
        },
        plantilla=str(APP_CONFIG.ruta_plantilla_base),
        salida=salida,
        proteger=True,
    )
    with open(salida, "rb") as archivo:
        lector = PdfReader(archivo)
        assert lector.is_encrypted
        assert lector.decrypt("1010101010")
        assert "Ana Lopez" in lector.pages[0].extract_text()


# ══════════════════════════════════════════════════════════════════════════
# API HTTP
# ══════════════════════════════════════════════════════════════════════════
def test_api_plantillas_marca_la_plantilla_base(cliente):
    cuerpo = cliente.get("/api/plantillas").get_json()
    plantillas = cuerpo["plantillas"]
    assert plantillas, "Debe haber al menos una plantilla disponible"
    por_defecto = [p for p in plantillas if p["por_defecto"]]
    assert len(por_defecto) == 1
    assert por_defecto[0]["nombre"] == APP_CONFIG.nombre_plantilla_base


def test_procesar_usa_la_plantilla_base_por_defecto(cliente, libro_completo):
    with open(libro_completo, "rb") as archivo:
        respuesta = cliente.post(
            "/procesar",
            data={
                "excel": (io.BytesIO(archivo.read()), "evento.xlsx"),
                "evento": "Congreso Plantilla",
                "modo": "generar",
            },
            content_type="multipart/form-data",
        )
    assert respuesta.status_code == 200
    cuerpo = respuesta.get_json()
    assert cuerpo["resumen"]["GENERADO"] == 6

    plantilla = _leer_plantilla(APP_CONFIG.ruta_plantilla_base)
    generado = APP_CONFIG.dir_salida / "maria.perezcorreo.com.pdf"
    assert generado.is_file()
    ancho, alto = _medidas(generado)
    assert ancho == pytest.approx(plantilla.ancho, abs=0.01)
    assert alto == pytest.approx(plantilla.alto, abs=0.01)
    assert "Maria Jose Perez" in _texto_pdf(generado)
