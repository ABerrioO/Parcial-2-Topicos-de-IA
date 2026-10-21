"""Carga y validación del archivo Excel de participantes (RF1, RF2).

El libro de entrada tiene cinco hojas, una por rol institucional:

``Asistentes``, ``Ponentes``, ``Conferenciantes``, ``Evaluadores`` y
``Organizadores``. Cada hoja debe traer los campos mínimos del rol
(README §5.2). Los encabezados reales pueden variar ("Email", "Nombre
Completo", "Cédula"…); el mapeo a los nombres canónicos lo resuelve el
módulo de IA (`modules.ia_validator.mapear_encabezados`).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List

import pandas as pd

from modules.ia_validator import mapear_encabezados

log = logging.getLogger(__name__)

# ── Definición del contrato de entrada ────────────────────────────────────
HOJAS_REQUERIDAS: List[str] = [
    "Asistentes",
    "Ponentes",
    "Conferenciantes",
    "Evaluadores",
    "Organizadores",
]

CAMPOS_POR_ROL: Dict[str, List[str]] = {
    "Asistentes": ["nombres", "apellidos", "correo"],
    "Ponentes": ["nombres", "apellidos", "correo", "documento", "ponencia"],
    "Conferenciantes": ["nombres", "apellidos", "correo", "documento", "conferencia"],
    "Evaluadores": ["nombres", "apellidos", "correo", "documento"],
    "Organizadores": ["nombres", "apellidos", "correo"],
}

#: Campos opcionales que se copian al certificado cuando existen.
CAMPOS_OPCIONALES: Dict[str, List[str]] = {
    "Ponentes": ["ponencia"],
    "Conferenciantes": ["conferencia"],
    "Evaluadores": ["area", "comite"],
    "Asistentes": ["tipo_participacion"],
    "Organizadores": ["cargo"],
}


class ErrorCargaExcel(ValueError):
    """Error de negocio: el archivo no cumple el contrato de entrada."""


# ── Carga ─────────────────────────────────────────────────────────────────
def cargar_excel(ruta: str | Path) -> Dict[str, pd.DataFrame]:
    """Carga un archivo Excel y devuelve un diccionario ``{hoja: DataFrame}``.

    Args:
        ruta: Ruta al libro ``.xlsx`` / ``.xlsm``.

    Raises:
        ErrorCargaExcel: Si el archivo no existe, no se puede leer o le
            faltan hojas requeridas.
    """
    ruta = Path(ruta)
    if not ruta.exists():
        raise ErrorCargaExcel(f"El archivo '{ruta.name}' no existe.")

    try:
        xls = pd.ExcelFile(ruta)
    except Exception as exc:  # pragma: no cover - depende del archivo corrupto
        raise ErrorCargaExcel(
            f"No se pudo leer el archivo Excel. Verifique que no esté dañado: {exc}"
        ) from exc

    hojas_existentes = [h for h in xls.sheet_names if h.strip() in HOJAS_REQUERIDAS]
    faltantes = [h for h in HOJAS_REQUERIDAS if h not in hojas_existentes]

    log.info("Hojas detectadas: %d/%d ✓", len(hojas_existentes), len(HOJAS_REQUERIDAS))
    if faltantes:
        raise ErrorCargaExcel(
            f"Faltan hojas requeridas: {', '.join(faltantes)}. "
            f"Encontradas: {', '.join(hojas_existentes) or 'ninguna'}."
        )

    datos: Dict[str, pd.DataFrame] = {}
    for hoja in HOJAS_REQUERIDAS:
        df = pd.read_excel(xls, sheet_name=hoja, dtype=object)
        df.columns = [str(c).strip() for c in df.columns]
        datos[hoja] = df

    return datos


# ── Validación estructural ────────────────────────────────────────────────
def _columnas_normalizadas(df: pd.DataFrame) -> List[str]:
    return [str(c).lower().strip() for c in df.columns]


def validar_campos(datos: Dict[str, pd.DataFrame]) -> List[str]:
    """Valida que cada hoja contenga los campos mínimos de su rol.

    Returns:
        Lista de errores (vacía si todo es correcto).
    """
    errores: List[str] = []
    for rol, df in datos.items():
        campos_req = CAMPOS_POR_ROL.get(rol, [])
        cols_lower = _columnas_normalizadas(df)
        for campo in campos_req:
            if campo not in cols_lower:
                errores.append(f"Hoja '{rol}' falta campo: {campo}")
    return errores


def normalizar_encabezados(datos: Dict[str, pd.DataFrame]) -> Dict[str, Dict[str, str]]:
    """Renombra las columnas a los nombres canónicos usando IA semántica.

    «Email» → ``correo``, «Nombre Completo» → ``nombres``, «Cédula» →
    ``documento``. Devuelve ``{hoja: {columna_original: columna_canonica}}``
    para trazabilidad de lo que se renombró.
    """
    renombres: Dict[str, Dict[str, str]] = {}
    for rol, df in datos.items():
        mapeo = mapear_encabezados(list(df.columns))
        existentes = {str(c).strip().lower() for c in df.columns}
        aplicado: Dict[str, str] = {}
        for origen, canon in mapeo.items():
            if canon != origen and canon in existentes:
                # Evita colisiones: no se renombra si el destino ya existe.
                continue
            aplicado[origen] = canon
        if aplicado:
            df.rename(columns=aplicado, inplace=True)
            log.info("Encabezados normalizados en '%s': %s", rol, aplicado)
        renombres[rol] = aplicado
    return renombres


def aplicar_mapeo_encabezados(
    datos: Dict[str, pd.DataFrame],
) -> Dict[str, Dict[str, str]]:
    """Alias de :func:`normalizar_encabezados` (compatibilidad RF2)."""
    return normalizar_encabezados(datos)


def validar_y_normalizar(
    datos: Dict[str, pd.DataFrame],
) -> tuple[Dict[str, pd.DataFrame], List[str], Dict[str, Dict[str, str]]]:
    """Aplica el mapeo semántico de encabezados y valida los campos.

    Returns:
        ``(datos, errores, renombres)``
    """
    renombres = normalizar_encabezados(datos)
    errores = validar_campos(datos)
    return datos, errores, renombres


def contar_participantes(datos: Dict[str, pd.DataFrame]) -> Dict[str, int]:
    """Número de filas útiles por rol (excluye filas totalmente vacías)."""
    conteo: Dict[str, int] = {}
    for rol, df in datos.items():
        vacias = df.isna().all(axis=1).sum() if len(df.columns) else 0
        conteo[rol] = int(len(df) - vacias)
    return conteo


def total_participantes(datos: Dict[str, pd.DataFrame]) -> int:
    """Total de participantes de todas las hojas."""
    return sum(contar_participantes(datos).values())
