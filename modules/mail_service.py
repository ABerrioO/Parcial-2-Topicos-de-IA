"""Servicio de envío de correos por SMTP institucional (RF4, RF5).

Características:
  * TLS (STARTTLS, puerto 587) o SSL implícito (puerto 465).
  * Reintentos con espera exponencial ante fallos transitorios.
  * Modo simulación (`SMTP_MODO_SIMULACION=True`): no abre conexión, pero
    registra el envío; útil para demostraciones sin credenciales reales.
  * Validación del correo destinatario antes de intentar el envío.
  * El cuerpo del mensaje es redactado por el módulo de IA.
"""

from __future__ import annotations

import logging
import os
import smtplib
import time
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email import encoders
from typing import Any, Dict

from config import SMTP_CONFIG
from modules.ia_validator import redactar_mensaje, validar_correo_ia

log = logging.getLogger(__name__)

#: Errores de SMTP que justifican reintentar.
ERRORES_TRANSITORIOS = (
    smtplib.SMTPServerDisconnected,
    smtplib.SMTPConnectError,
    smtplib.SMTPResponseException,
    TimeoutError,
    ConnectionError,
    OSError,
)


class ErrorEnvio(Exception):
    """Error de negocio al enviar un certificado."""


def construir_mensaje(
    destinatario: str,
    nombre: str,
    archivo_pdf: str,
    evento: str,
    rol: str = "Participante",
    dependencia: str = "Oficina de Eventos Académicos",
    cuerpo_html: str | None = None,
    asunto: str | None = None,
) -> MIMEMultipart:
    """Construye el mensaje MIME con el certificado adjunto."""
    from_name = SMTP_CONFIG.from_name
    usuario = SMTP_CONFIG.user or "certificados@lasalle.edu.co"

    if asunto is None or cuerpo_html is None:
        mensaje_ia = redactar_mensaje(nombre, rol, evento, dependencia)
        asunto = asunto or mensaje_ia["asunto"]
        cuerpo_html = cuerpo_html or mensaje_ia["cuerpo_html"]

    msg = MIMEMultipart()
    msg["From"] = f"{from_name} <{usuario}>"
    msg["To"] = destinatario
    msg["Subject"] = asunto

    msg.attach(MIMEText(cuerpo_html, "html", "utf-8"))

    with open(archivo_pdf, "rb") as archivo:
        parte = MIMEBase("application", "pdf")
        parte.set_payload(archivo.read())
    encoders.encode_base64(parte)
    nombre_archivo = os.path.basename(archivo_pdf)
    parte.add_header("Content-Disposition", f'attachment; filename="{nombre_archivo}"')
    msg.attach(parte)

    return msg


def enviar_certificado(
    destinatario: str,
    nombre: str,
    archivo_pdf: str,
    evento: str,
    rol: str = "Participante",
    dependencia: str = "Oficina de Eventos Académicos",
    reintentos: int | None = None,
) -> Dict[str, Any]:
    """Envía el certificado por correo usando el SMTP institucional con TLS.

    Args:
        destinatario: Correo del participante.
        nombre: Nombre legible del participante.
        archivo_pdf: Ruta del certificado generado.
        evento: Nombre del evento (asunto del correo).
        rol: Rol del participante dentro del evento.
        dependencia: Dependencia firmante del correo.
        reintentos: Intentos adicionales ante errores transitorios.

    Returns:
        ``{"estado": "OK"|"ERROR", "correo": str, "detalle": str}``
    """
    destinatario = str(destinatario or "").strip()
    nombre = str(nombre or "").strip()

    if not validar_correo_ia(destinatario):
        detalle = f"Correo destinatario inválido: '{destinatario}'"
        log.error("[SMTP] %s", detalle)
        return {"estado": "ERROR", "correo": destinatario, "detalle": detalle}

    if not os.path.exists(archivo_pdf):
        detalle = f"No se encontró el certificado: '{archivo_pdf}'"
        log.error("[SMTP] %s", detalle)
        return {"estado": "ERROR", "correo": destinatario, "detalle": detalle}

    if SMTP_CONFIG.modo_simulacion:
        log.info("[SMTP] (simulación) Enviando a %s ... OK", destinatario)
        return {
            "estado": "OK",
            "correo": destinatario,
            "detalle": "Simulación: mensaje no transmitido",
        }

    if not SMTP_CONFIG.configurado:
        detalle = "SMTP no configurado (faltan SMTP_HOST, SMTP_USER o SMTP_PASS)."
        log.error("[SMTP] %s", detalle)
        return {"estado": "ERROR", "correo": destinatario, "detalle": detalle}

    if not SMTP_CONFIG.seguro:
        log.warning(
            "[SMTP] Enviando sin cifrado de transporte a %s:%s — active SMTP_USE_TLS.",
            SMTP_CONFIG.host,
            SMTP_CONFIG.port,
        )

    msg = construir_mensaje(
        destinatario, nombre, archivo_pdf, evento, rol=rol, dependencia=dependencia
    )

    intentos = max(1, (SMTP_CONFIG.max_reintentos if reintentos is None else reintentos))
    ultimo_error: Exception | None = None

    for intento in range(1, intentos + 1):
        try:
            log.info("[SMTP] Enviando a %s ... ", destinatario)
            with _conectar() as servidor:
                servidor.send_message(msg)
            log.info("[SMTP] Enviado a %s ✓", destinatario)
            return {"estado": "OK", "correo": destinatario, "detalle": ""}
        except smtplib.SMTPAuthenticationError as exc:
            detalle = f"Error de autenticación SMTP: {exc.smtp_error or exc}"
            log.error("[SMTP] %s", detalle)
            return {"estado": "ERROR", "correo": destinatario, "detalle": detalle}
        except Exception as exc:  # noqa: BLE001 - se reintenta si es transitorio
            ultimo_error = exc
            log.warning(
                "[SMTP] Intento %d/%d fallido para %s: %s",
                intento,
                intentos,
                destinatario,
                exc,
            )
            if intento < intentos and isinstance(exc, ERRORES_TRANSITORIOS):
                time.sleep(min(2 ** (intento - 1), 8))
                continue
            break

    detalle = str(ultimo_error) if ultimo_error else "Error desconocido al enviar."
    log.error("[SMTP] Fallo definitivo para %s: %s", destinatario, detalle)
    return {"estado": "ERROR", "correo": destinatario, "detalle": detalle}


def _conectar() -> smtplib.SMTP:
    """Abre la conexión SMTP con TLS/SSL y autentica la sesión."""
    host = SMTP_CONFIG.host
    puerto = SMTP_CONFIG.port
    timeout = SMTP_CONFIG.timeout

    if SMTP_CONFIG.use_ssl or puerto == 465:
        servidor: smtplib.SMTP = smtplib.SMTP_SSL(host, puerto, timeout=timeout)
    else:
        servidor = smtplib.SMTP(host, puerto, timeout=timeout)
        if SMTP_CONFIG.use_tls:
            servidor.starttls()

    servidor.login(SMTP_CONFIG.user, SMTP_CONFIG.password)
    return servidor


def verificar_conexion() -> Dict[str, Any]:
    """Comprueba la conectividad y la autenticación con el servidor SMTP.

    Útil para la pantalla de diagnóstico de la aplicación web.
    """
    if SMTP_CONFIG.modo_simulacion:
        return {
            "estado": "SIMULACION",
            "detalle": "Modo simulación activo: no se abre conexión al servidor.",
            "servidor": f"{SMTP_CONFIG.host}:{SMTP_CONFIG.port}",
        }
    if not SMTP_CONFIG.configurado:
        return {
            "estado": "ERROR",
            "detalle": "Faltan credenciales SMTP (SMTP_HOST, SMTP_USER, SMTP_PASS).",
            "servidor": f"{SMTP_CONFIG.host}:{SMTP_CONFIG.port}",
        }
    try:
        with _conectar() as servidor:
            servidor.noop()
        return {
            "estado": "OK",
            "detalle": "Conexión y autenticación correctas.",
            "servidor": f"{SMTP_CONFIG.host}:{SMTP_CONFIG.port}",
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "estado": "ERROR",
            "detalle": str(exc),
            "servidor": f"{SMTP_CONFIG.host}:{SMTP_CONFIG.port}",
        }
