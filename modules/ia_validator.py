"""Módulo de IA aplicada — PLN, similitud fuzzy y validación semántica.

Este módulo concentra las técnicas de IA descritas en el README §6:

============  ==========================================================
Técnica IA    Aplicación en el sistema
============  ==========================================================
PLN           Normalización de nombres propios (acentos, capitalización,
              partículas, espacios múltiples).
Similitud     Detección de duplicados por correos y por nombres.
PLN semántico Mapeo de encabezados equivalentes ("Email" → ``correo``).
Heurística    Detección de anomalías (correos, nombres, documentos).
IA generativa Redacción asistida de mensajes de correo (opcional).
============  ==========================================================

La parte generativa es **opcional**: si no hay `LLM_API_KEY` configurada se
utilizan plantillas institucionales deterministas, de modo que el sistema
funciona sin conexión y sin costo.
"""

from __future__ import annotations

import json
import logging
import os
import re
import unicodedata
import urllib.error
import urllib.request
from typing import Any, Dict, Iterable, List, Sequence, Tuple

import pandas as pd
from fuzzywuzzy import fuzz

from config import IA_CONFIG

log = logging.getLogger(__name__)

# ── Vocabulario lingüístico ───────────────────────────────────────────────
#: Partículas que en español van en minúscula dentro de un nombre compuesto.
PARTICULAS_MINUSCULA = {
    "de", "del", "la", "las", "los", "y", "e", "da", "do", "dos", "di",
    "van", "von", "der", "den", "ter", "ten",
}

#: Prefijos que conservan su forma abreviada ("Mc", "Mac").
PREFIJOS_ESPECIALES = {"mc": "Mc", "mac": "Mac", "van": "van", "von": "von"}

#: Caracteres no permitidos en nombres propios (dígitos, símbolos).
RE_CARACTERES_NOMBRE = re.compile(r"[^A-Za-zÁÉÍÓÚÑáéíóúñü' \-\.]")

#: Sinónimos aceptados para mapear encabezados a campos canónicos.
SINONIMOS_ENCABEZADOS: Dict[str, List[str]] = {
    "nombres": [
        "nombre", "nombres", "nombre completo", "nombres completos",
        "nombres y apellidos", "first name", "nombres del participante",
    ],
    "apellidos": [
        "apellido", "apellidos", "apellidos del participante",
        "last name", "apellidos completos",
    ],
    "correo": [
        "email", "correo", "correo electronico", "e-mail", "mail",
        "correo institucional", "correo electronico institucional",
    ],
    "documento": [
        "cedula", "documento", "documento de identidad", "id", "cc",
        "numero de documento", "num documento", "cedula de ciudadania",
    ],
    "ponencia": ["ponencia", "titulo de la ponencia", "titulo ponencia", "ponenciaSHA"],
    "conferencia": ["conferencia", "titulo de la conferencia", "charla", "conferencia SHA"],
    "area": ["area", "area de evaluacion", "area tematica"],
    "comite": ["comite", "comite evaluador", "comite academico"],
    "tipo_participacion": ["tipo de participacion", "tipo participacion", "modalidad"],
    "cargo": ["cargo", "rol institucional", "puesto"],
}


# ══════════════════════════════════════════════════════════════════════════
# 1. PLN — Normalización de nombres
# ══════════════════════════════════════════════════════════════════════════
def normalizar_nombre(nombre: Any, preservar_enie: bool | None = None) -> str:
    """Normaliza un nombre propio (PLN básico).

    Pasos: recorta espacios, descompone Unicode (NFD), elimina diacríticos,
    capitaliza según reglas del español y colapsa espacios repetidos.

    Ejemplos:
        >>> normalizar_nombre("  maría  jose pérez ")
        'Maria Jose Perez'
        >>> normalizar_nombre("juan de la cruz gómez")
        'Juan de la Cruz Gomez'
    """
    if nombre is None or (isinstance(nombre, float) and pd.isna(nombre)):
        return ""
    if not isinstance(nombre, str) and pd.isna(nombre):
        return ""

    texto = str(nombre).strip()
    if not texto:
        return ""

    if preservar_enie is None:
        preservar_enie = IA_CONFIG.preservar_enie

    # Protege la eñe si el llamador lo requiere.
    marcadores = {"ñ": "\u0001", "Ñ": "\u0002"}
    if preservar_enie:
        for original, marca in marcadores.items():
            texto = texto.replace(original, marca)

    # Descomposición Unicode + eliminación de marcas diacríticas.
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")

    if preservar_enie:
        for original, marca in marcadores.items():
            texto = texto.replace(marca, original.lower() if original == "ñ" else original)

    # Colapsa espacios y capitaliza con partículas en minúscula.
    texto = re.sub(r"\s+", " ", texto).strip()
    return _capitalizar_espanol(texto)


def _capitalizar_espanol(texto: str) -> str:
    """Capitaliza una frase propia aplicando partículas en minúscula."""
    palabras = texto.split(" ")
    salida: List[str] = []
    for indice, palabra in enumerate(palabras):
        base = palabra.lower()
        if base in PREFIJOS_ESPECIALES:
            salida.append(PREFIJOS_ESPECIALES[base])
        elif indice > 0 and base in PARTICULAS_MINUSCULA:
            salida.append(base)
        else:
            salida.append(palabra[:1].upper() + palabra[1:] if palabra else palabra)
    return " ".join(salida)


def normalizar_nombre_completo(nombres: Any, apellidos: Any) -> str:
    """Combina y normaliza nombres + apellidos en un solo texto."""
    return normalizar_nombre(f"{nombres or ''} {apellidos or ''}".strip())


def limpiar_texto(valor: Any) -> str:
    """Convierte cualquier valor de celda en texto limpio (sin NaN)."""
    if valor is None:
        return ""
    if isinstance(valor, float) and pd.isna(valor):
        return ""
    try:
        if pd.isna(valor):
            return ""
    except (TypeError, ValueError):
        pass
    return str(valor).strip()


# ══════════════════════════════════════════════════════════════════════════
# 2. Similitud fuzzy — Detección de duplicados
# ══════════════════════════════════════════════════════════════════════════
def _comparar(cadena_a: str, cadena_b: str) -> int:
    """Similitud 0-100 entre dos cadenas (Levenshtein vía fuzzywuzzy)."""
    if not cadena_a or not cadena_b:
        return 0
    if cadena_a == cadena_b:
        return 100
    return int(fuzz.ratio(cadena_a, cadena_b))


def detectar_duplicados(df: pd.DataFrame, umbral: int = 90) -> List[Tuple[int, int, int]]:
    """Detecta correos duplicados o muy similares (IA: fuzzy matching).

    Args:
        df: DataFrame con al menos la columna ``correo``.
        umbral: Porcentaje mínimo de similitud (0-100) para considerar
            duplicado.

    Returns:
        Lista de tuplas ``(indice_i, indice_j, score)``.
    """
    if df is None or df.empty or "correo" not in df.columns:
        return []

    correos = [normalizar_correo(c) for c in df["correo"].tolist()]
    duplicados: List[Tuple[int, int, int]] = []

    for i in range(len(correos)):
        if not correos[i]:
            continue
        for j in range(i + 1, len(correos)):
            if not correos[j]:
                continue
            score = _comparar(correos[i], correos[j])
            if score >= umbral:
                duplicados.append((i, j, score))

    return duplicados


def detectar_duplicados_nombres(
    df: pd.DataFrame, umbral: int | None = None
) -> List[Tuple[int, int, int]]:
    """Detecta nombres completos duplicados o muy similares."""
    if umbral is None:
        umbral = IA_CONFIG.umbral_nombres
    if df is None or df.empty:
        return []
    if not {"nombres", "apellidos"}.issubset(df.columns):
        return []

    nombres = [
        normalizar_nombre_completo(n, a)
        for n, a in zip(df["nombres"].tolist(), df["apellidos"].tolist())
    ]
    duplicados: List[Tuple[int, int, int]] = []
    for i in range(len(nombres)):
        if not nombres[i]:
            continue
        for j in range(i + 1, len(nombres)):
            if not nombres[j]:
                continue
            score = _comparar(nombres[i], nombres[j])
            if score >= umbral:
                duplicados.append((i, j, score))
    return duplicados


def analizar_duplicados(df: pd.DataFrame, umbral: int | None = None) -> List[Dict[str, Any]]:
    """Devuelve los duplicados con detalle legible para la UI y el reporte.

    Cada elemento incluye el tipo de coincidencia, las filas involucradas,
    los correos comparados y el porcentaje de similitud.
    """
    if umbral is None:
        umbral = IA_CONFIG.umbral_duplicados

    hallazgos: List[Dict[str, Any]] = []
    vistos: set[tuple[int, int]] = set()

    for i, j, score in detectar_duplicados(df, umbral):
        clave = ("correo", i, j)
        if clave in vistos:
            continue
        vistos.add(clave)
        hallazgos.append(
            {
                "tipo": "correo",
                "filas": [int(i), int(j)],
                "similitud": int(score),
                "valores": [
                    limpiar_texto(df.iloc[i].get("correo")),
                    limpiar_texto(df.iloc[j].get("correo")),
                ],
                "nombres": [
                    _nombre_legible(df.iloc[i]),
                    _nombre_legible(df.iloc[j]),
                ],
            }
        )

    for i, j, score in detectar_duplicados_nombres(df):
        clave = ("nombre", i, j)
        if clave in vistos:
            continue
        vistos.add(clave)
        hallazgos.append(
            {
                "tipo": "nombre",
                "filas": [int(i), int(j)],
                "similitud": int(score),
                "valores": [_nombre_legible(df.iloc[i]), _nombre_legible(df.iloc[j])],
                "nombres": [_nombre_legible(df.iloc[i]), _nombre_legible(df.iloc[j])],
            }
        )

    return hallazgos


def _nombre_legible(fila: pd.Series) -> str:
    """Nombre completo legible de una fila (para reportes)."""
    nombres = limpiar_texto(fila.get("nombres"))
    apellidos = limpiar_texto(fila.get("apellidos"))
    return normalizar_nombre(f"{nombres} {apellidos}".strip())


# ══════════════════════════════════════════════════════════════════════════
# 3. Validación semántica de correo
# ══════════════════════════════════════════════════════════════════════════
RE_CORREO = re.compile(r"^[\w\.\-\+]+@[\w\-]+(\.[\w\-]+)+$")


def normalizar_correo(correo: Any) -> str:
    """Minúsculas y sin espacios en un correo."""
    return limpiar_texto(correo).lower().replace(" ", "")


def validar_correo_ia(correo: Any) -> bool:
    """Valida semánticamente el formato de un correo electrónico.

    Además del patrón regex comprueba: longitud razonable, ausencia de
    puntos consecutivos y que el dominio tenga una extensión válida.
    """
    valor = limpiar_texto(correo).lower()
    if not valor or len(valor) > 254:
        return False
    if " " in valor or ".." in valor or valor.startswith(".") or "@." in valor:
        return False
    if not RE_CORREO.match(valor):
        return False

    local, _, dominio = valor.partition("@")
    if not local or len(local) > 64:
        return False
    if "." not in dominio or dominio.startswith(".") or dominio.endswith("."):
        return False

    tld = dominio.rsplit(".", 1)[-1]
    return len(tld) >= 2 and tld.isalpha()


# ══════════════════════════════════════════════════════════════════════════
# 4. Mapeo semántico de encabezados
# ══════════════════════════════════════════════════════════════════════════
def _clave_comparacion(texto: str) -> str:
    """Clave de comparación sin tildes, mayúsculas ni signos."""
    descompuesto = unicodedata.normalize("NFD", str(texto).lower().strip())
    sin_marcas = "".join(c for c in descompuesto if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", sin_marcas).strip()


def mapear_encabezados(columnas: Sequence[str]) -> Dict[str, str]:
    """Mapea encabezados equivalentes a campos canónicos (PLN semántico).

    Ejemplos:
        'Nombre Completo' → ``nombres``
        'Email' / 'e-mail' → ``correo``
        'Cédula' / 'CC' → ``documento``
    """
    mapeo: Dict[str, str] = {}
    for col in columnas:
        col_l = _clave_comparacion(col)
        if not col_l:
            continue
        mejor_canon, mejor_score = "", 0
        for canon, variantes in SINONIMOS_ENCABEZADOS.items():
            for variante in variantes:
                score = _comparar(col_l, _clave_comparacion(variante))
                if score > mejor_score:
                    mejor_canon, mejor_score = canon, score
        if mejor_canon and mejor_score >= IA_CONFIG.umbral_encabezados:
            mapeo[col] = mejor_canon
    return mapeo


def sugerir_encabezados(columnas: Sequence[str]) -> List[Dict[str, Any]]:
    """Sugerencias de mapeo con el puntaje, para mostrar en la interfaz."""
    sugerencias: List[Dict[str, Any]] = []
    for col in columnas:
        col_l = _clave_comparacion(col)
        mejor_canon, mejor_score = "", 0
        for canon, variantes in SINONIMOS_ENCABEZADOS.items():
            for variante in variantes:
                score = _comparar(col_l, _clave_comparacion(variante))
                if score > mejor_score:
                    mejor_canon, mejor_score = canon, score
        sugerencias.append(
            {
                "columna": col,
                "propuesto": mejor_canon or None,
                "similitud": int(mejor_score),
                "aplicado": mejor_score >= IA_CONFIG.umbral_encabezados,
            }
        )
    return sugerencias


# ══════════════════════════════════════════════════════════════════════════
# 5. Detección de anomalías
# ══════════════════════════════════════════════════════════════════════════
def detectar_anomalias(fila: pd.Series | Dict[str, Any]) -> List[str]:
    """Detecta anomalías en una fila de participante.

    Aplica reglas + heurísticas: correo ausente o inválido, nombres vacíos,
    caracteres no permitidos en nombres y documento de longitud atípica.
    """
    anomalias: List[str] = []

    def obtener(clave: str) -> Any:
        if isinstance(fila, dict):
            return fila.get(clave)
        return fila.get(clave)

    nombres = limpiar_texto(obtener("nombres"))
    apellidos = limpiar_texto(obtener("apellidos"))
    correo = normalizar_correo(obtener("correo"))
    documento = limpiar_texto(obtener("documento"))

    if not nombres:
        anomalias.append("El campo 'nombres' está vacío.")
    if not apellidos:
        anomalias.append("El campo 'apellidos' está vacío.")
    if not correo:
        anomalias.append("El campo 'correo' está vacío.")
    elif not validar_correo_ia(correo):
        anomalias.append(f"El correo '{correo}' no tiene un formato válido.")

    for campo, valor in (("nombres", nombres), ("apellidos", apellidos)):
        if valor and RE_CARACTERES_NOMBRE.search(valor):
            anomalias.append(
                f"El campo '{campo}' contiene caracteres no permitidos: '{valor}'."
            )

    if documento:
        longitud = len(re.sub(r"\D", "", documento))
        if longitud and not (
            IA_CONFIG.longitud_documento_min <= longitud <= IA_CONFIG.longitud_documento_max
        ):
            anomalias.append(
                f"El documento '{documento}' tiene una longitud atípica ({longitud} dígitos)."
            )

    return anomalias


def filas_validas(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Separa el DataFrame en filas sin anomalías y filas con anomalías."""
    if df is None or df.empty:
        return df, df
    indices_ok, indices_problema = [], []
    for idx, fila in df.iterrows():
        if detectar_anomalias(fila):
            indices_problema.append(idx)
        else:
            indices_ok.append(idx)
    return df.loc[indices_ok], df.loc[indices_problema]


# ══════════════════════════════════════════════════════════════════════════
# 6. IA generativa — redacción asistida de mensajes (opcional)
# ══════════════════════════════════════════════════════════════════════════
_PLANTILLA_ASUNTO = "Certificado de participación — {evento} | Universidad de La Salle"

_PLANTILLA_CUERPO = """\
<p>Estimado(a) {nombre},</p>
<p>Adjunto encontrará su certificado de participación como <strong>{rol}</strong>
del evento <strong>{evento}</strong>.</p>
<p>Recuerde conservar este correo como respaldo del documento.</p>
<p>Cordialmente,<br><strong>Universidad de La Salle</strong><br>
{dependencia}</p>
"""

_PLANTILLA_CUERPO_ERROR = """\
<p>Estimado(a) {nombre},</p>
<p>Ha ocurrido un problema al generar su certificado del evento
<strong>{evento}</strong>. Por favor comuníquese con {dependencia}
para recibir la asistencia correspondiente.</p>
<p>Disculpe las molestias.</p>
<p>Cordialmente,<br><strong>Universidad de La Salle</strong></p>
"""


def redactar_mensaje(
    nombre: str,
    rol: str,
    evento: str,
    dependencia: str = "Oficina de Eventos Académicos",
    error: bool = False,
    usar_llm: bool | None = None,
) -> Dict[str, str]:
    """Redacta el mensaje del certificado (IA generativa con respaldo local).

    Si ``LLM_API_KEY`` está configurada y ``usar_llm`` es True, consulta una
    API compatible con OpenAI y devuelve el mensaje generado. Ante cualquier
    fallo de red o de formato se cae de vuelta a la plantilla institucional,
    de modo que el envío nunca se detiene por un problema de la IA.

    Returns:
        ``{"asunto", "cuerpo_html", "cuerpo_texto", "origen"}``
    """
    if usar_llm is None:
        usar_llm = bool(os.getenv("LLM_API_KEY"))

    if usar_llm:
        generado = _redactar_con_llm(nombre, rol, evento, dependencia, error)
        if generado:
            generado["origen"] = "IA generativa"
            return generado

    asunto = _PLANTILLA_ASUNTO.format(evento=evento)
    cuerpo = (_PLANTILLA_CUERPO_ERROR if error else _PLANTILLA_CUERPO).format(
        nombre=nombre or "participante",
        rol=rol,
        evento=evento,
        dependencia=dependencia,
    )
    return {
        "asunto": asunto,
        "cuerpo_html": cuerpo,
        "cuerpo_texto": _html_a_texto(cuerpo),
        "origen": "plantilla institucional",
    }


def _redactar_con_llm(
    nombre: str, rol: str, evento: str, dependencia: str, error: bool
) -> Dict[str, str] | None:
    """Consulta un LLM compatible con OpenAI (falla de forma silenciosa)."""
    api_key = os.getenv("LLM_API_KEY", "")
    base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    modelo = os.getenv("LLM_MODEL", "gpt-4o-mini")
    if not api_key:
        return None

    instruccion = (
        "Redacta un correo institucional breve y respetuoso, en español, "
        "para adjuntar un certificado académico. Devuelve JSON válido con "
        "las claves 'asunto' y 'cuerpo'. Sin emojis ni encabezados markdown."
    )
    if error:
        instruccion = (
            "Redacta un correo institucional breve y respetuoso, en español, "
            "informando que hubo un problema al generar un certificado. "
            "Devuelve JSON válido con las claves 'asunto' y 'cuerpo'. "
            "Sin emojis ni encabezados markdown."
        )

    carga = {
        "model": modelo,
        "temperature": 0.4,
        "messages": [
            {"role": "system", "content": instruccion},
            {
                "role": "user",
                "content": (
                    f"Nombre: {nombre}\nRol: {rol}\nEvento: {evento}\n"
                    f"Dependencia: {dependencia}"
                ),
            },
        ],
    }

    try:
        peticion = urllib.request.Request(
            f"{base_url}/chat/completions",
            data=json.dumps(carga).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )
        with urllib.request.urlopen(peticion, timeout=20) as respuesta:
            datos = json.loads(respuesta.read().decode("utf-8"))
        contenido = datos["choices"][0]["message"]["content"].strip()
        if contenido.startswith("```"):
            contenido = contenido.strip("`")
            contenido = contenido.split("\n", 1)[-1] if "\n" in contenido else contenido
        objeto = json.loads(contenido)
        asunto = str(objeto.get("asunto") or _PLANTILLA_ASUNTO.format(evento=evento))
        cuerpo_html = str(objeto.get("cuerpo") or "")
        return {
            "asunto": asunto,
            "cuerpo_html": cuerpo_html,
            "cuerpo_texto": _html_a_texto(cuerpo_html),
        }
    except (urllib.error.URLError, TimeoutError, KeyError, ValueError, OSError) as exc:
        log.warning("[IA] Fallo al consultar el LLM, se usa plantilla local: %s", exc)
        return None


def _html_a_texto(html: str) -> str:
    """Convierte HTML simple a texto plano (para la parte alternativa)."""
    texto = re.sub(r"<br\s*/?>", "\n", html)
    texto = re.sub(r"</p>", "\n\n", texto)
    texto = re.sub(r"<[^>]+>", "", texto)
    return re.sub(r"\n{3,}", "\n\n", texto).strip()


def dependencias_disponibles() -> Dict[str, bool]:
    """Indica qué capacidades de IA están activas en la instalación."""
    return {
        "pln": True,
        "fuzzy": True,
        "llm": bool(os.getenv("LLM_API_KEY")),
    }
