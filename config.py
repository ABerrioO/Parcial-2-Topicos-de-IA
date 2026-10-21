"""Configuración general de **Certificado Unilasallista**.

Centraliza:
  * Rutas base del proyecto (plantillas, estáticos, datos, salidas).
  * Parámetros del servicio de correo (SMTP) leídos de variables de entorno.
  * Umbrales de los módulos de IA (similitud, normalización, anomalías).
  * Configuración de logging con los prefijos `[INFO] [IA] [PDF] [SMTP] [DB]`
    usados en el informe de pruebas (README §7.2).

Las credenciales **nunca** se hardcodean: se leen de `.env` / entorno.
"""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# ── Rutas base ────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _ruta(valor: str, por_defecto: Path) -> Path:
    """Resuelve una ruta relativa contra la raíz del proyecto."""
    p = Path(valor)
    return p if p.is_absolute() else (BASE_DIR / p)


def _bool(valor: str | None, por_defecto: bool = False) -> bool:
    if valor is None:
        return por_defecto
    return str(valor).strip().lower() in {"1", "true", "t", "yes", "y", "si", "sí"}


def _int(valor: str | None, por_defecto: int) -> int:
    try:
        return int(str(valor).strip())
    except (TypeError, ValueError):
        return por_defecto


# ── Configuración de correo ───────────────────────────────────────────────
@dataclass(frozen=True)
class SMTPConfig:
    """Parámetros del servidor de correo institucional."""

    host: str = field(default_factory=lambda: os.getenv("SMTP_HOST", "smtp.office365.com"))
    port: int = field(default_factory=lambda: _int(os.getenv("SMTP_PORT"), 587))
    user: str = field(default_factory=lambda: os.getenv("SMTP_USER", ""))
    password: str = field(default_factory=lambda: os.getenv("SMTP_PASS", ""))
    from_name: str = field(
        default_factory=lambda: os.getenv("SMTP_FROM_NAME", "Certificados Unilasallista")
    )
    use_tls: bool = field(default_factory=lambda: _bool(os.getenv("SMTP_USE_TLS"), True))
    use_ssl: bool = field(default_factory=lambda: _bool(os.getenv("SMTP_USE_SSL"), False))
    timeout: int = field(default_factory=lambda: _int(os.getenv("SMTP_TIMEOUT"), 30))
    max_reintentos: int = field(default_factory=lambda: _int(os.getenv("SMTP_MAX_REINTENTOS"), 3))
    modo_simulacion: bool = field(
        default_factory=lambda: _bool(os.getenv("SMTP_MODO_SIMULACION"), True)
    )

    @property
    def configurado(self) -> bool:
        """True si hay host y usuario disponibles para autenticar."""
        return bool(self.host and self.user and self.password)

    @property
    def seguro(self) -> bool:
        """True si el transporte está cifrado (TLS o SSL)."""
        return self.use_tls or self.use_ssl or self.port == 465


# ── Configuración de IA ───────────────────────────────────────────────────
@dataclass(frozen=True)
class IAConfig:
    """Umbrales y opciones de los módulos de IA aplicada."""

    umbral_duplicados: int = field(
        default_factory=lambda: _int(os.getenv("UMBRAL_DUPLICADOS"), 90)
    )
    umbral_encabezados: int = field(
        default_factory=lambda: _int(os.getenv("UMBRAL_ENCABEZADOS"), 85)
    )
    umbral_nombres: int = field(default_factory=lambda: _int(os.getenv("UMBRAL_NOMBRES"), 92))
    preservar_enie: bool = field(
        default_factory=lambda: _bool(os.getenv("PLN_PRESERVAR_ENIE"), False)
    )
    longitud_documento_min: int = field(
        default_factory=lambda: _int(os.getenv("DOCUMENTO_LONGITUD_MIN"), 5)
    )
    longitud_documento_max: int = field(
        default_factory=lambda: _int(os.getenv("DOCUMENTO_LONGITUD_MAX"), 20)
    )


# ── Configuración de la aplicación ────────────────────────────────────────
@dataclass(frozen=True)
class AppConfig:
    """Rutas, tamaño máximo de carga y opciones de la aplicación Flask."""

    secret_key: str = field(
        default_factory=lambda: os.getenv("SECRET_KEY", "clave-de-desarrollo-no-usar-en-produccion")
    )
    db_path: Path = field(default_factory=lambda: _ruta(os.getenv("DB_PATH", "certificados.db"), BASE_DIR / "certificados.db"))
    dir_salida: Path = field(default_factory=lambda: BASE_DIR / "out")
    dir_temporal: Path = field(default_factory=lambda: BASE_DIR / "tmp")
    dir_plantillas: Path = field(default_factory=lambda: BASE_DIR / "templates")
    dir_estaticos: Path = field(default_factory=lambda: BASE_DIR / "static")
    dir_datos: Path = field(default_factory=lambda: BASE_DIR / "data")
    nombre_plantilla_base: str = field(
        default_factory=lambda: os.getenv("PLANTILLA_BASE", "certificado_base.pdf")
    )
    max_content_length: int = field(
        default_factory=lambda: _int(os.getenv("MAX_UPLOAD_MB"), 20) * 1024 * 1024
    )
    extensiones_permitidas: tuple[str, ...] = (".xlsx", ".xlsm")
    proteger_pdf: bool = field(default_factory=lambda: _bool(os.getenv("PDF_PROTEGER"), False))
    fecha_certificado: str = field(
        default_factory=lambda: os.getenv("FECHA_CERTIFICADO", "13 de noviembre del 2026")
    )

    @property
    def ruta_plantilla_base(self) -> Path:
        """Ruta de la plantilla institucional usada por defecto."""
        return self.dir_plantillas / self.nombre_plantilla_base

    def asegurar_directorios(self) -> None:
        """Crea los directorios de trabajo si no existen."""
        for d in (self.dir_salida, self.dir_temporal, self.dir_datos):
            d.mkdir(parents=True, exist_ok=True)


# ── Instancias singleton ──────────────────────────────────────────────────
SMTP_CONFIG = SMTPConfig()
IA_CONFIG = IAConfig()
APP_CONFIG = AppConfig()


# ── Logging ───────────────────────────────────────────────────────────────
class _PrefijoFormatter(logging.Formatter):
    """Formatter que antepone el prefijo de la categoría al mensaje."""

    PREFIJOS = {
        "app": "[INFO]",
        "modules.excel_loader": "[EXCEL]",
        "modules.ia_validator": "[IA]",
        "modules.pdf_generator": "[PDF]",
        "modules.mail_service": "[SMTP]",
        "modules.tracker": "[DB]",
        "werkzeug": "[WEB]",
    }

    def format(self, record: logging.LogRecord) -> str:
        prefijo = self.PREFIJOS.get(record.name, "[INFO]")
        return f"{prefijo} {record.getMessage()}"


def setup_logging(nivel: int = logging.INFO) -> logging.Logger:
    """Configura el logging de consola una sola vez."""
    raiz = logging.getLogger()
    if any(getattr(h, "_certificado_unilasallista", False) for h in raiz.handlers):
        return logging.getLogger("app")

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_PrefijoFormatter("%(message)s"))
    handler._certificado_unilasallista = True  # type: ignore[attr-defined]

    raiz.handlers.clear()
    raiz.addHandler(handler)
    raiz.setLevel(nivel)
    return logging.getLogger("app")


logger = setup_logging()
