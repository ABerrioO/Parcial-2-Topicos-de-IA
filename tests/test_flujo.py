"""Pruebas del flujo completo: Excel → IA → PDF → SMTP → trazabilidad.

Reproducen los diez casos del informe de pruebas (README §7.1).
"""

from __future__ import annotations

import io
import zipfile

import pandas as pd
import pytest

from modules import tracker
from modules.excel_loader import (
    ErrorCargaExcel,
    cargar_excel,
    validar_campos,
    validar_y_normalizar,
)
from modules.mail_service import enviar_certificado
from modules.pdf_generator import generar_certificado


# ══════════════════════════════════════════════════════════════════════════
# Caso 1 y 2 — Carga del Excel
# ══════════════════════════════════════════════════════════════════════════
def test_caso_01_carga_excel_valido(libro_completo):
    datos = cargar_excel(libro_completo)
    assert len(datos) == 5
    assert set(datos) == {
        "Asistentes",
        "Ponentes",
        "Conferenciantes",
        "Evaluadores",
        "Organizadores",
    }
    assert validar_campos(datos) == []


def test_caso_02_excel_sin_hojas(libro_incompleto):
    with pytest.raises(ErrorCargaExcel) as error:
        cargar_excel(libro_incompleto)
    mensaje = str(error.value)
    assert "Faltan hojas requeridas" in mensaje
    assert "Ponentes" in mensaje


def test_carga_archivo_inexistente():
    with pytest.raises(ErrorCargaExcel):
        cargar_excel("no_existe.xlsx")


def test_validar_campos_detecta_faltantes():
    df = pd.DataFrame({"nombres": ["a"], "correo": ["a@b.co"]})
    errores = validar_campos({"Asistentes": df})
    assert errores == ["Hoja 'Asistentes' falta campo: apellidos"]


def test_mapeo_semantico_de_encabezados(tmp_path):
    ruta = tmp_path / "variantes.xlsx"
    with pd.ExcelWriter(ruta, engine="openpyxl") as escritor:
        pd.DataFrame(
            {
                "Nombre Completo": ["Juan"],
                "Apellidos": ["Pérez"],
                "Email": ["juan@correo.com"],
                "Cédula": ["101010"],
            }
        ).to_excel(escritor, sheet_name="Asistentes", index=False)
        pd.DataFrame(
            {
                "Nombre Completo": ["Ana"],
                "Apellidos": ["Diaz"],
                "Email": ["ana@correo.com"],
                "Cédula": ["202020"],
                "Ponencia": ["Tema"],
            }
        ).to_excel(escritor, sheet_name="Ponentes", index=False)
        pd.DataFrame(
            {
                "nombres": ["Luis"],
                "apellidos": ["Paz"],
                "correo": ["luis@correo.com"],
                "documento": ["303030"],
                "conferencia": ["Charla"],
            }
        ).to_excel(escritor, sheet_name="Conferenciantes", index=False)
        pd.DataFrame(
            {
                "nombres": ["Sara"],
                "apellidos": ["Gil"],
                "correo": ["sara@correo.com"],
                "documento": ["404040"],
            }
        ).to_excel(escritor, sheet_name="Evaluadores", index=False)
        pd.DataFrame(
            {"nombres": ["Eva"], "apellidos": ["Rios"], "correo": ["eva@correo.com"]}
        ).to_excel(escritor, sheet_name="Organizadores", index=False)

    datos = cargar_excel(ruta)
    datos, errores, renombres = validar_y_normalizar(datos)
    assert errores == []
    assert renombres["Asistentes"]["Email"] == "correo"
    assert renombres["Asistentes"]["Cédula"] == "documento"
    assert "correo" in datos["Asistentes"].columns


# ══════════════════════════════════════════════════════════════════════════
# Caso 7 — Generación del PDF
# ══════════════════════════════════════════════════════════════════════════
def test_caso_07_generacion_pdf(tmp_path):
    salida = tmp_path / "certificado.pdf"
    datos = {
        "nombres": "Maria Jose",
        "apellidos": "Perez",
        "rol": "Ponente",
        "evento": "Congreso 2026",
        "ponencia": "PLN en la educación",
        "fecha": "22 de octubre de 2026",
        "codigo": "CU-1234ABCD",
    }
    ruta = generar_certificado(datos, plantilla=None, salida=salida)
    assert ruta.endswith(".pdf")
    assert salida.exists()
    assert salida.stat().st_size > 1000
    with open(salida, "rb") as archivo:
        assert archivo.read(4) == b"%PDF"


def test_generacion_pdf_con_plantilla(tmp_path):
    plantilla = tmp_path / "base.pdf"
    generar_certificado(
        {"nombres": "Ana", "apellidos": "Lopez", "rol": "Asistente", "evento": "Evento"},
        plantilla=None,
        salida=plantilla,
    )
    salida = tmp_path / "con_plantilla.pdf"
    generar_certificado(
        {"nombres": "Ana", "apellidos": "Lopez", "rol": "Asistente", "evento": "Evento"},
        plantilla=str(plantilla),
        salida=salida,
    )
    assert salida.exists() and salida.stat().st_size > 1000


# ══════════════════════════════════════════════════════════════════════════
# Casos 8 y 9 — Envío SMTP (modo simulación) y registro
# ══════════════════════════════════════════════════════════════════════════
def test_caso_08_envio_exitoso(tmp_path, entorno_temporal):
    pdf = tmp_path / "c.pdf"
    generar_certificado(
        {"nombres": "Ana", "apellidos": "Lopez", "rol": "Asistente", "evento": "Evento"},
        plantilla=None,
        salida=pdf,
    )
    respuesta = enviar_certificado("ana@correo.com", "Ana Lopez", str(pdf), "Evento")
    assert respuesta["estado"] == "OK"

    tracker.registrar_envio("Evento", "Asistente", "Ana Lopez", "ana@correo.com", "OK")
    assert tracker.ya_enviado("Evento", "ana@correo.com") is True


def test_caso_09_envio_fallido_por_correo_invalido(tmp_path, entorno_temporal):
    pdf = tmp_path / "c.pdf"
    generar_certificado(
        {"nombres": "Ana", "apellidos": "Lopez", "rol": "Asistente", "evento": "Evento"},
        plantilla=None,
        salida=pdf,
    )
    respuesta = enviar_certificado("correo-malo", "Ana", str(pdf), "Evento")
    assert respuesta["estado"] == "ERROR"
    assert "inválido" in respuesta["detalle"].lower()


def test_envio_fallido_por_pdf_inexistente(entorno_temporal):
    respuesta = enviar_certificado("ana@correo.com", "Ana", "no_existe.pdf", "Evento")
    assert respuesta["estado"] == "ERROR"
    assert "certificado" in respuesta["detalle"].lower()


# ══════════════════════════════════════════════════════════════════════════
# Caso 10 — Control de duplicados en la trazabilidad
# ══════════════════════════════════════════════════════════════════════════
def test_caso_10_reenvio_duplicado_se_omite(entorno_temporal):
    tracker.registrar_envio("Evento", "Asistente", "Ana Lopez", "ana@correo.com", "OK")
    assert tracker.ya_enviado("Evento", "ana@correo.com") is True
    assert tracker.ya_enviado("Otro evento", "ana@correo.com") is False


def test_estadisticas_consolidan_estados(entorno_temporal):
    tracker.registrar_envio("Evento", "Asistente", "A", "a@correo.com", "OK")
    tracker.registrar_envio("Evento", "Ponente", "B", "b@correo.com", "ERROR", "fallo")
    tracker.registrar_envio("Evento", "Ponente", "C", "c@correo.com", "OMITIDO")

    stats = tracker.estadisticas("Evento")
    assert stats["total"] == 3
    assert stats["por_estado"]["OK"] == 1
    assert stats["por_estado"]["ERROR"] == 1
    assert stats["por_estado"]["OMITIDO"] == 1
    assert stats["por_rol"]["Ponente"] == 2


# ══════════════════════════════════════════════════════════════════════════
# API HTTP — flujo completo desde la interfaz
# ══════════════════════════════════════════════════════════════════════════
def test_api_salud(cliente):
    respuesta = cliente.get("/api/salud")
    assert respuesta.status_code == 200
    cuerpo = respuesta.get_json()
    assert cuerpo["ok"] is True
    assert "smtp" in cuerpo and "ia" in cuerpo


def test_api_validar_detecta_anomalias_y_duplicados(cliente, tmp_path):
    ruta = tmp_path / "casos.xlsx"
    with pd.ExcelWriter(ruta, engine="openpyxl") as escritor:
        pd.DataFrame(
            {
                "nombres": ["juan", "juan", ""],
                "apellidos": ["perez", "perez", "x"],
                "correo": [
                    "juan.perez@uni.edu.co",
                    "juan.perez@uni.edu.com",
                    "correo-malo",
                ],
            }
        ).to_excel(escritor, sheet_name="Asistentes", index=False)
        for hoja in ("Ponentes", "Conferenciantes", "Evaluadores", "Organizadores"):
            pd.DataFrame(
                {"nombres": ["x"], "apellidos": ["y"], "correo": ["z@correo.com"]}
            ).to_excel(escritor, sheet_name=hoja, index=False)

    with open(ruta, "rb") as archivo:
        respuesta = cliente.post(
            "/api/validar",
            data={"excel": (io.BytesIO(archivo.read()), "casos.xlsx")},
            content_type="multipart/form-data",
        )
    assert respuesta.status_code == 200
    cuerpo = respuesta.get_json()
    assert cuerpo["ok"] is True
    assert cuerpo["resumen"]["total_participantes"] == 7
    assert cuerpo["resumen"]["duplicados"] >= 1
    assert cuerpo["resumen"]["anomalias"] >= 1


def test_api_procesar_flujo_completo(cliente, libro_completo):
    with open(libro_completo, "rb") as archivo:
        respuesta = cliente.post(
            "/procesar",
            data={
                "excel": (io.BytesIO(archivo.read()), "evento.xlsx"),
                "evento": "Congreso 2026",
                "dependencia": "Facultad de Ingeniería",
                "plantilla": "",
            },
            content_type="multipart/form-data",
        )
    assert respuesta.status_code == 200
    cuerpo = respuesta.get_json()
    assert cuerpo["ok"] is True
    assert cuerpo["total"] == 6
    assert cuerpo["resumen"]["OK"] == 6
    assert cuerpo["resumen"]["ERROR"] == 0

    envios = tracker.listar_envios(evento="Congreso 2026")
    assert len(envios) == 6
    assert all(e["estado"] == "OK" for e in envios)


def test_api_procesar_omite_envios_duplicados(cliente, libro_completo):
    contenido = libro_completo.read_bytes()
    datos = {
        "excel": (io.BytesIO(contenido), "evento.xlsx"),
        "evento": "Congreso Repetido",
        "dependencia": "Dependencia",
        "plantilla": "",
    }
    primera = cliente.post(
        "/procesar", data=datos, content_type="multipart/form-data"
    ).get_json()
    datos["excel"] = (io.BytesIO(contenido), "evento.xlsx")
    segunda = cliente.post(
        "/procesar", data=datos, content_type="multipart/form-data"
    ).get_json()

    assert primera["resumen"]["OK"] == 6
    assert segunda["resumen"]["OK"] == 0
    assert segunda["resumen"]["OMITIDO"] == 6


def test_api_procesar_rechaza_extension_invalida(cliente):
    respuesta = cliente.post(
        "/procesar",
        data={
            "excel": (io.BytesIO(b"contenido"), "evento.txt"),
            "evento": "Evento",
        },
        content_type="multipart/form-data",
    )
    assert respuesta.status_code == 400
    assert respuesta.get_json()["ok"] is False


def test_api_procesar_exige_evento(cliente, libro_completo):
    with open(libro_completo, "rb") as archivo:
        respuesta = cliente.post(
            "/procesar",
            data={
                "excel": (io.BytesIO(archivo.read()), "evento.xlsx"),
                "evento": "",
            },
            content_type="multipart/form-data",
        )
    assert respuesta.status_code == 400


def test_api_procesar_registra_error_de_correo_invalido(cliente, tmp_path):
    ruta = tmp_path / "malo.xlsx"
    with pd.ExcelWriter(ruta, engine="openpyxl") as escritor:
        pd.DataFrame(
            {
                "nombres": ["sin"],
                "apellidos": ["correo"],
                "correo": ["sin-dominio@"],
            }
        ).to_excel(escritor, sheet_name="Asistentes", index=False)
        for hoja in ("Ponentes", "Conferenciantes", "Evaluadores", "Organizadores"):
            pd.DataFrame(
                {
                    "nombres": ["x"],
                    "apellidos": ["y"],
                    "correo": ["z@correo.com"],
                    "documento": ["12345678"],
                    "ponencia": ["Tema"],
                    "conferencia": ["Charla"],
                }
            ).to_excel(escritor, sheet_name=hoja, index=False)

    with open(ruta, "rb") as archivo:
        respuesta = cliente.post(
            "/procesar",
            data={
                "excel": (io.BytesIO(archivo.read()), "malo.xlsx"),
                "evento": "Evento con error",
            },
            content_type="multipart/form-data",
        )
    cuerpo = respuesta.get_json()
    assert cuerpo["ok"] is True
    assert cuerpo["resumen"]["ERROR"] == 1

    envios = tracker.listar_envios(evento="Evento con error")
    estados = {e["estado"] for e in envios}
    assert "ERROR" in estados


def test_api_trazabilidad_y_estadisticas(cliente, libro_completo):
    with open(libro_completo, "rb") as archivo:
        cliente.post(
            "/procesar",
            data={
                "excel": (io.BytesIO(archivo.read()), "evento.xlsx"),
                "evento": "Evento Trazable",
            },
            content_type="multipart/form-data",
        )

    envios = cliente.get("/api/envios?evento=Evento Trazable").get_json()
    assert envios["total"] == 6

    stats = cliente.get("/api/estadisticas?evento=Evento Trazable").get_json()
    assert stats["estadisticas"]["total"] == 6
    assert stats["estadisticas"]["tasa_exito"] == 100.0

    eventos = cliente.get("/api/eventos").get_json()
    assert any(e["nombre"] == "Evento Trazable" for e in eventos["eventos"])


def test_interfaz_principal_carga(cliente):
    respuesta = cliente.get("/")
    assert respuesta.status_code == 200
    assert "Certificado Unilasallista" in respuesta.get_data(as_text=True)
    assert "btn-generar" in respuesta.get_data(as_text=True)
    assert "modal-visor" in respuesta.get_data(as_text=True)


def test_modo_generar_sin_enviar_y_ver_certificado(cliente, libro_completo):
    with open(libro_completo, "rb") as archivo:
        respuesta = cliente.post(
            "/procesar",
            data={
                "excel": (io.BytesIO(archivo.read()), "evento.xlsx"),
                "evento": "Congreso Solo Generar",
                "dependencia": "Facultad de Ingeniería",
                "modo": "generar",
            },
            content_type="multipart/form-data",
        )
    assert respuesta.status_code == 200
    cuerpo = respuesta.get_json()
    assert cuerpo["ok"] is True
    assert cuerpo["modo"] == "generacion"
    assert cuerpo["resumen"]["GENERADO"] == 6

    # Verificar que el PDF se puede ver en el navegador (inline)
    correo_muestra = cuerpo["detalle"][0]["correo"]
    res_visor = cliente.get(f"/certificados/{correo_muestra}")
    assert res_visor.status_code == 200
    assert res_visor.headers["Content-Type"] == "application/pdf"
    assert "inline" in res_visor.headers.get("Content-Disposition", "")

    # Verificar descarga con parámetro descargar=1
    res_descarga = cliente.get(f"/certificados/{correo_muestra}?descargar=1")
    assert res_descarga.status_code == 200
    assert "attachment" in res_descarga.headers.get("Content-Disposition", "")

    # Verificar api de certificados disponibles
    res_api = cliente.get("/api/certificados").get_json()
    assert res_api["ok"] is True
    assert res_api["total"] >= 6

