"""Punto de entrada de la aplicación web **Certificado Unilasallista**.

Flujo completo (README §3.3)::

    Carga Excel → Validación IA → Plantilla → Generar PDF → Envío SMTP → Registro

Rutas disponibles
-----------------
``GET  /``                        Interfaz web.
``POST /procesar``                Procesa un evento completo (envía correos).
``POST /api/validar``             Solo valida y reporta (sin enviar).
``GET  /api/salud``               Estado del servicio.
``GET  /api/config``              Configuración efectiva (sin secretos).
``GET  /api/plantillas``          Plantillas disponibles.
``GET  /api/envios``              Trazabilidad de envíos.
``GET  /api/estadisticas``        Resumen estadístico.
``GET  /api/eventos``             Eventos registrados.
``POST /api/smtp/verificar``      Prueba de conexión SMTP.
``GET  /certificados/<correo>``   Descarga del PDF generado.
"""

from __future__ import annotations

import logging
import os
import time
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

from flask import Flask, jsonify, render_template, request, send_from_directory
from werkzeug.utils import secure_filename

from config import APP_CONFIG, IA_CONFIG, SMTP_CONFIG
from modules import tracker
from modules.excel_loader import (
    ErrorCargaExcel,
    cargar_excel,
    contar_participantes,
    total_participantes,
    validar_y_normalizar,
)
from modules.ia_validator import (
    analizar_duplicados,
    dependencias_disponibles,
    detectar_anomalias,
    normalizar_nombre,
    validar_correo_ia,
)
from modules.mail_service import enviar_certificado, verificar_conexion
from modules.pdf_generator import generar_certificado

log = logging.getLogger("app")

APP_CONFIG.asegurar_directorios()
tracker.inicializar_db()

app = Flask(__name__)
app.config["SECRET_KEY"] = APP_CONFIG.secret_key
app.config["MAX_CONTENT_LENGTH"] = APP_CONFIG.max_content_length
app.config["JSON_SORT_KEYS"] = False
app.config["TEMPLATES_AUTO_RELOAD"] = True


# ══════════════════════════════════════════════════════════════════════════
# Utilidades
# ══════════════════════════════════════════════════════════════════════════
def _nombre_seguro(nombre: str) -> str:
    """Normaliza un nombre de archivo generado por el usuario."""
    base = secure_filename(nombre or "")
    if not base:
        base = unicodedata.normalize("NFKD", nombre or "archivo").encode("ascii", "ignore").decode()
    return base or "archivo"


def _extension_valida(nombre: str) -> bool:
    return Path(nombre).suffix.lower() in APP_CONFIG.extensiones_permitidas


def _plantilla_solicitada(valor: str | None) -> str | None:
    """Resuelve la plantilla pedida contra el directorio de plantillas.

    Sin valor explícito se usa la plantilla institucional por defecto
    (``templates/certificado_base.pdf``); si el usuario elige el diseño
    propio se devuelve ``None``. Solo se aceptan archivos PDF ubicados
    dentro de ``templates/``.
    """
    if valor is not None and not str(valor).strip():
        return None  # diseño propio, sin plantilla

    raiz = APP_CONFIG.dir_plantillas.resolve()
    candidatas = [
        Path(valor) if valor else APP_CONFIG.ruta_plantilla_base,
        APP_CONFIG.dir_plantillas / Path(valor).name if valor else None,
        APP_CONFIG.dir_plantillas / valor if valor else None,
    ]
    for candidata in candidatas:
        if candidata is None:
            continue
        try:
            if candidata.suffix.lower() != ".pdf" or not candidata.is_file():
                continue
            if candidata.resolve().is_relative_to(raiz):
                return str(candidata)
        except OSError:  # pragma: no cover - rutas inválidas
            continue
    return None


def _respuesta_error(mensaje: str, codigo: int = 400, extra: Dict[str, Any] | None = None):
    cuerpo: Dict[str, Any] = {"ok": False, "mensaje": mensaje}
    if extra:
        cuerpo.update(extra)
    return jsonify(cuerpo), codigo


# ══════════════════════════════════════════════════════════════════════════
# Interfaz y estado
# ══════════════════════════════════════════════════════════════════════════
@app.route("/")
def index():
    """Interfaz web principal."""
    return render_template(
        "index.html",
        umbrales={
            "duplicados": IA_CONFIG.umbral_duplicados,
            "encabezados": IA_CONFIG.umbral_encabezados,
        },
        smtp={
            "host": SMTP_CONFIG.host,
            "puerto": SMTP_CONFIG.port,
            "usuario": SMTP_CONFIG.user,
            "modo_simulacion": SMTP_CONFIG.modo_simulacion,
            "configurado": SMTP_CONFIG.configurado,
        },
    )


@app.route("/api/salud")
def api_salud():
    """Estado del servicio y de sus dependencias."""
    return jsonify(
        {
            "ok": True,
            "servicio": "Certificado Unilasallista",
            "version": "1.0.0",
            "ia": dependencias_disponibles(),
            "smtp": {
                "host": SMTP_CONFIG.host,
                "puerto": SMTP_CONFIG.port,
                "modo_simulacion": SMTP_CONFIG.modo_simulacion,
                "configurado": SMTP_CONFIG.configurado,
                "transporte_seguro": SMTP_CONFIG.seguro,
            },
            "base_datos": str(tracker.ruta_db()),
        }
    )


@app.route("/api/config")
def api_config():
    """Configuración efectiva. Nunca expone contraseñas."""
    return jsonify(
        {
            "ok": True,
            "app": {
                "directorio_salida": str(APP_CONFIG.dir_salida),
                "directorio_temporal": str(APP_CONFIG.dir_temporal),
                "max_upload_mb": APP_CONFIG.max_content_length // (1024 * 1024),
                "extensiones_permitidas": list(APP_CONFIG.extensiones_permitidas),
                "pdf_protegido": APP_CONFIG.proteger_pdf,
            },
            "ia": {
                "umbral_duplicados": IA_CONFIG.umbral_duplicados,
                "umbral_encabezados": IA_CONFIG.umbral_encabezados,
                "preservar_enie": IA_CONFIG.preservar_enie,
            },
            "smtp": {
                "host": SMTP_CONFIG.host,
                "puerto": SMTP_CONFIG.port,
                "usuario": SMTP_CONFIG.user,
                "modo_simulacion": SMTP_CONFIG.modo_simulacion,
                "timeout": SMTP_CONFIG.timeout,
                "max_reintentos": SMTP_CONFIG.max_reintentos,
            },
        }
    )


@app.route("/api/plantillas")
def api_plantillas():
    """Plantillas PDF disponibles en el servidor."""
    base = APP_CONFIG.ruta_plantilla_base
    plantillas = []
    if APP_CONFIG.dir_plantillas.exists():
        for archivo in sorted(APP_CONFIG.dir_plantillas.glob("*.pdf")):
            plantillas.append(
                {
                    "nombre": archivo.name,
                    "ruta": str(archivo),
                    "tamano_kb": round(archivo.stat().st_size / 1024, 1),
                    "por_defecto": archivo.resolve() == base.resolve(),
                }
            )
    return jsonify({"ok": True, "plantillas": plantillas})


@app.route("/api/smtp/verificar", methods=["POST"])
def api_smtp_verificar():
    """Prueba de conexión con el servidor de correo."""
    return jsonify({"ok": True, **verificar_conexion()})


# ══════════════════════════════════════════════════════════════════════════
# Validación (sin envío)
# ══════════════════════════════════════════════════════════════════════════
@app.route("/api/validar", methods=["POST"])
def api_validar():
    """Valida el Excel y devuelve el informe de IA, sin enviar nada."""
    archivo = request.files.get("excel")
    if archivo is None or not archivo.filename:
        return _respuesta_error("Debe adjuntar un archivo Excel (.xlsx).")
    if not _extension_valida(archivo.filename):
        return _respuesta_error(
            f"Extensión no permitida. Se aceptan: {', '.join(APP_CONFIG.extensiones_permitidas)}."
        )

    APP_CONFIG.dir_temporal.mkdir(parents=True, exist_ok=True)
    ruta_tmp = APP_CONFIG.dir_temporal / f"validacion_{int(time.time())}_{_nombre_seguro(archivo.filename)}"
    archivo.save(ruta_tmp)

    try:
        informe = _analizar_archivo(ruta_tmp)
    except ErrorCargaExcel as exc:
        return _respuesta_error(str(exc))
    finally:
        _eliminar(ruta_tmp)

    return jsonify({"ok": True, **informe})


def _analizar_archivo(ruta_excel: Path) -> Dict[str, Any]:
    """Carga, normaliza y analiza el Excel sin enviar certificados."""
    datos = cargar_excel(ruta_excel)
    datos, errores_campos, renombres = validar_y_normalizar(datos)

    por_rol: List[Dict[str, Any]] = []
    total_anomalias = 0
    total_duplicados = 0

    for rol, df in datos.items():
        df = df.copy()
        if "nombres" in df.columns:
            df["nombres_norm"] = df["nombres"].apply(normalizar_nombre)
            log.info("[IA] Normalizando %d nombres en '%s'...", len(df), rol)
        if "apellidos" in df.columns:
            df["apellidos_norm"] = df["apellidos"].apply(normalizar_nombre)

        duplicados = analizar_duplicados(df)
        total_duplicados += len(duplicados)
        if duplicados:
            log.warning("[IA] Detectados %d posibles duplicados en %s", len(duplicados), rol)

        anomalias: List[Dict[str, Any]] = []
        for indice, fila in df.iterrows():
            problemas = detectar_anomalias(fila)
            if problemas:
                anomalias.append(
                    {
                        "fila": int(indice) + 2,  # +2: encabezado de Excel + base 1
                        "correo": str(fila.get("correo", "") or ""),
"nombre": " ".join(
                    [
                        str(fila.get("nombres", "") or ""),
                        str(fila.get("apellidos", "") or ""),
                    ]
                ).strip(),
                        "problemas": problemas,
                    }
                )
        total_anomalias += len(anomalias)

        por_rol.append(
            {
                "rol": rol,
                "participantes": int(len(df)),
                "duplicados": duplicados,
                "anomalias": anomalias,
                "encabezados": sorted(str(c) for c in df.columns),
                "mapeo": renombres.get(rol, {}),
            }
        )

    return {
        "resumen": {
            "total_participantes": total_participantes(datos),
            "por_rol": contar_participantes(datos),
            "duplicados": total_duplicados,
            "anomalias": total_anomalias,
            "errores_campos": errores_campos,
        },
        "roles": por_rol,
    }


# ══════════════════════════════════════════════════════════════════════════
# Procesamiento completo
# ══════════════════════════════════════════════════════════════════════════
@app.route("/procesar", methods=["POST"])
def procesar():
    """Procesa un evento: valida, genera los PDF y envía los certificados."""
    archivo = request.files.get("excel")
    if archivo is None or not archivo.filename:
        return _respuesta_error("Debe adjuntar un archivo Excel (.xlsx).")
    if not _extension_valida(archivo.filename):
        return _respuesta_error(
            f"Extensión no permitida. Se aceptan: {', '.join(APP_CONFIG.extensiones_permitidas)}."
        )

    evento = (request.form.get("evento") or "").strip()
    if not evento:
        return _respuesta_error("Debe indicar el nombre del evento.")

    dependencia = (request.form.get("dependencia") or "Dependencia organizadora").strip()
    plantilla = _plantilla_solicitada(request.form.get("plantilla"))
    modo = str(request.form.get("modo", "enviar")).lower()
    solo_validar = modo in {"validar", "solo", "dry-run"}
    solo_generar = modo in {"generar", "solo_generar", "sin_enviar"}

    APP_CONFIG.dir_temporal.mkdir(parents=True, exist_ok=True)
    ruta_tmp = APP_CONFIG.dir_temporal / f"proceso_{int(time.time())}_{_nombre_seguro(archivo.filename)}"
    archivo.save(ruta_tmp)

    started = time.time()
    try:
        datos = cargar_excel(ruta_tmp)
        datos, errores_campos, renombres = validar_y_normalizar(datos)
    except ErrorCargaExcel as exc:
        _eliminar(ruta_tmp)
        return _respuesta_error(str(exc))

    if errores_campos:
        _eliminar(ruta_tmp)
        return jsonify(
            {
                "ok": False,
                "mensaje": "El archivo no cumple con los campos requeridos.",
                "errores": errores_campos,
            }
        ), 400

    tracker.registrar_evento(evento, dependencia)

    resultados: List[Dict[str, Any]] = []
    advertencias: List[str] = []
    pdfs_generados: List[Path] = []

    for rol, df in datos.items():
        df = df.copy()
        if "nombres" in df.columns:
            df["nombres_norm"] = df["nombres"].apply(normalizar_nombre)
        if "apellidos" in df.columns:
            df["apellidos_norm"] = df["apellidos"].apply(normalizar_nombre)

        duplicados = analizar_duplicados(df)
        if duplicados:
            advertencias.append(
                f"Posibles duplicados en {rol}: " + ", ".join(
                    f"{d['valores'][0]} ~ {d['valores'][1]} ({d['similitud']}%)"
                    for d in duplicados[:5]
                )
            )
            log.warning("[IA] Detectados %d posibles duplicados en %s", len(duplicados), rol)

        for _, fila in df.iterrows():
            correo = str(fila.get("correo", "") or "").strip()
            nombres = str(fila.get("nombres_norm", "") or "")
            apellidos = str(fila.get("apellidos_norm", "") or "")
            nombre_completo = f"{nombres} {apellidos}".strip()

            if not validar_correo_ia(correo):
                detalle = f"Correo inválido: '{correo}'"
                tracker.registrar_envio(evento, rol, nombre_completo, correo, "ERROR", detalle, dependencia)
                resultados.append(
                    {"correo": correo, "nombre": nombre_completo, "rol": rol,
                     "estado": "ERROR", "detalle": detalle}
                )
                continue

            if tracker.ya_enviado(evento, correo) and not solo_generar:
                resultados.append(
                    {"correo": correo, "nombre": nombre_completo, "rol": rol,
                     "estado": "OMITIDO", "detalle": "Ya enviado en este evento"}
                )
                continue

            if solo_validar:
                resultados.append(
                    {"correo": correo, "nombre": nombre_completo, "rol": rol,
                     "estado": "PENDIENTE", "detalle": "Modo validación: no se envió"}
                )
                continue

            datos_certificado = {
                "nombres": nombres,
                "apellidos": apellidos,
                "rol": rol,
                "evento": evento,
                "fecha": APP_CONFIG.fecha_certificado,
                "codigo": _codigo_certificado(evento, correo),
                "dependencia": dependencia,
            }
            for campo in (
                "ponencia",
                "conferencia",
                "area",
                "comite",
                "documento",
                "cargo",
                "curso",
                "promedio",
                "reconocimiento",
                "mencion",
                "tipo_participacion",
            ):
                valor = fila.get(campo)
                if valor is not None and str(valor).strip() not in {"", "nan", "None"}:
                    datos_certificado[campo] = str(valor).strip()

            nombre_pdf = _nombre_seguro(correo) + ".pdf"
            ruta_pdf = APP_CONFIG.dir_salida / nombre_pdf

            try:
                generar_certificado(datos_certificado, plantilla=plantilla, salida=ruta_pdf)
                pdfs_generados.append(ruta_pdf)
            except Exception as exc:  # noqa: BLE001
                detalle = f"Error generando el PDF: {exc}"
                tracker.registrar_envio(evento, rol, nombre_completo, correo, "ERROR", detalle, dependencia)
                resultados.append(
                    {"correo": correo, "nombre": nombre_completo, "rol": rol,
                     "estado": "ERROR", "detalle": detalle}
                )
                continue

            if solo_generar:
                detalle = "Certificado generado exitosamente (sin enviar)"
                tracker.registrar_envio(evento, rol, nombre_completo, correo, "GENERADO", detalle, dependencia)
                resultados.append(
                    {
                        "correo": correo,
                        "nombre": nombre_completo,
                        "rol": rol,
                        "estado": "GENERADO",
                        "detalle": detalle,
                        "archivo": nombre_pdf,
                    }
                )
                continue

            respuesta = enviar_certificado(
                correo, nombre_completo, str(ruta_pdf), evento, rol=rol, dependencia=dependencia
            )
            estado = "OK" if respuesta.get("estado") == "OK" else "ERROR"
            tracker.registrar_envio(
                evento, rol, nombre_completo, correo, estado, respuesta.get("detalle", ""), dependencia
            )
            resultados.append(
                {
                    "correo": correo,
                    "nombre": nombre_completo,
                    "rol": rol,
                    "estado": estado,
                    "detalle": respuesta.get("detalle", ""),
                    "archivo": nombre_pdf,
                }
            )

    _eliminar(ruta_tmp)

    conteo = {"OK": 0, "ERROR": 0, "OMITIDO": 0, "PENDIENTE": 0, "GENERADO": 0}
    for r in resultados:
        conteo[r["estado"]] = conteo.get(r["estado"], 0) + 1

    log.info(
        "[INFO] Total procesados: %d | OK: %d | ERROR: %d | OMITIDO: %d | GENERADO: %d",
        len(resultados),
        conteo["OK"],
        conteo["ERROR"],
        conteo["OMITIDO"],
        conteo["GENERADO"],
    )

    limpiar = str(request.form.get("limpiar", "0")).lower() in {"1", "true", "si"}
    if not solo_validar and not solo_generar and limpiar:
        _limpiar_pdfs(pdfs_generados)

    modo_nombre = "validacion" if solo_validar else ("generacion" if solo_generar else "envio")
    return jsonify(
        {
            "ok": True,
            "modo": modo_nombre,
            "evento": evento,
            "dependencia": dependencia,
            "total": len(resultados),
            "resumen": conteo,
            "advertencias": advertencias,
            "detalle": resultados,
            "duracion_seg": round(time.time() - started, 2),
        }
    )


# ══════════════════════════════════════════════════════════════════════════
# Trazabilidad
# ══════════════════════════════════════════════════════════════════════════
@app.route("/api/envios")
def api_envios():
    """Listado de envíos con filtros por evento y estado."""
    evento = request.args.get("evento")
    estado = request.args.get("estado")
    limite = int(request.args.get("limite", 200))
    offset = int(request.args.get("offset", 0))
    envios = tracker.listar_envios(evento=evento, estado=estado, limite=limite, offset=offset)
    return jsonify({"ok": True, "total": len(envios), "envios": envios})


@app.route("/api/estadisticas")
def api_estadisticas():
    """Estadísticas de trazabilidad."""
    return jsonify({"ok": True, "estadisticas": tracker.estadisticas(request.args.get("evento"))})


@app.route("/api/eventos")
def api_eventos():
    """Eventos registrados en la base."""
    return jsonify({"ok": True, "eventos": tracker.listar_eventos()})


@app.route("/certificados/<path:correo>")
def descargar_certificado(correo: str):
    """Visualiza en el navegador o descarga el certificado generado."""
    directorio = str(APP_CONFIG.dir_salida)
    
    nombres_a_probar = [
        _nombre_seguro(correo),
        _nombre_seguro(correo) + ".pdf",
        correo,
        correo + ".pdf",
    ]
    if correo.lower().endswith(".pdf"):
        nombres_a_probar.append(_nombre_seguro(correo[:-4]) + ".pdf")

    archivo_encontrado = None
    for n in nombres_a_probar:
        if (APP_CONFIG.dir_salida / n).is_file():
            archivo_encontrado = n
            break

    if not archivo_encontrado:
        return _respuesta_error("No se encontró el certificado solicitado.", 404)

    descargar = request.args.get("descargar", "0").lower() in {"1", "true", "si"}
    return send_from_directory(
        directorio,
        archivo_encontrado,
        as_attachment=descargar,
        mimetype="application/pdf",
        download_name=archivo_encontrado if descargar else None,
    )


@app.route("/api/certificados")
def api_certificados():
    """Listado de certificados PDF generados y disponibles en el servidor."""
    certificados = []
    if APP_CONFIG.dir_salida.exists():
        for ruta in sorted(APP_CONFIG.dir_salida.glob("*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True):
            certificados.append(
                {
                    "archivo": ruta.name,
                    "tamano_kb": round(ruta.stat().st_size / 1024, 1),
                    "fecha": datetime.fromtimestamp(ruta.stat().st_mtime).isoformat(sep=" ", timespec="seconds"),
                    "url": f"/certificados/{ruta.name}",
                }
            )
    return jsonify({"ok": True, "total": len(certificados), "certificados": certificados})


# ══════════════════════════════════════════════════════════════════════════
# Auxiliares
# ══════════════════════════════════════════════════════════════════════════
def _codigo_certificado(evento: str, correo: str) -> str:
    """Código corto y legible del certificado (traabilidad en el PDF)."""
    import hashlib

    digest = hashlib.sha1(f"{evento}|{correo}".encode("utf-8")).hexdigest()[:8]
    return f"CU-{digest.upper()}"


def _eliminar(ruta: str | Path) -> None:
    """Borra un archivo temporal ignorando errores."""
    try:
        Path(ruta).unlink(missing_ok=True)
    except OSError:  # pragma: no cover
        pass


def _limpiar_pdfs(pdfs: List[Path]) -> None:
    """Elimina los PDF temporales tras el envío (README §8)."""
    for pdf in pdfs:
        _eliminar(pdf)


# ── Manejo de errores ─────────────────────────────────────────────────────
@app.errorhandler(413)
def error_413(error):  # noqa: ANN001
    limite_mb = APP_CONFIG.max_content_length // (1024 * 1024)
    return _respuesta_error(f"El archivo supera el límite de {limite_mb} MB.", 413)


@app.errorhandler(500)
def error_500(error):  # noqa: ANN001
    log.exception("[ERROR] Error interno del servidor")
    return _respuesta_error("Error interno del servidor.", 500)


if __name__ == "__main__":
    puerto = int(os.getenv("PORT", 5000))
    depuracion = os.getenv("FLASK_DEBUG", "0") in {"1", "true", "True"}
    log.info("[INFO] Certificado Unilasallista escuchando en http://127.0.0.1:%d", puerto)
    app.run(host=os.getenv("HOST", "127.0.0.1"), port=puerto, debug=depuracion)
