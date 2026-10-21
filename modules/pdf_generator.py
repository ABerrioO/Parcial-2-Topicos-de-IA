"""Generación de certificados PDF con `reportlab` y `pypdf` (RF3).

Cada certificado se compone de dos capas:

  * La **plantilla institucional** (``templates/certificado_base.pdf``), que
    se usa como página base del PDF.  De ella se lee la geometría (tamaño de
    página) y la posición de cada texto.
  * El **texto dinámico** del participante, superpuesto sobre la plantilla en
    los mismos lugares donde el diseño declara sus marcadores:
    ``<NOMBRE>``, ``<PROMEDIO>``, ``<CURSO>``, ``<EVENTO>``, ``<FECHA>`` y
    ``<DEPENDENCIA>``.

Así, reemplazar el archivo ``templates/certificado_base.pdf`` basta para que
los certificados salgan con el diseño nuevo: el generador no tiene ningún
texto fijo incrustado en la plantilla.

Cuando la plantilla no existe (o no declara marcadores) se recurre al diseño
propio dibujado con reportlab, que se conserva como respaldo.

Opcionalmente el PDF se cifra con contraseña (por defecto el número de
documento del participante), conforme a la política de datos del README §8.
"""

from __future__ import annotations

import io
import logging
import math
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from config import APP_CONFIG

try:  # `pypdf` permite componer la plantilla PDF con el texto dinámico.
    from pypdf import PdfReader, PdfWriter

    PPDF_DISPONIBLE = True
except ImportError:  # pragma: no cover - dependencia opcional
    PdfReader = None  # type: ignore[assignment]
    PdfWriter = None  # type: ignore[assignment]
    PPDF_DISPONIBLE = False

log = logging.getLogger(__name__)

#: Colores corporativos Unilasallista
COLOR_INSTITUCIONAL = (7 / 255, 69 / 255, 99 / 255)  # #074563
COLOR_TEXTO = (31 / 255, 41 / 255, 55 / 255)         # #1f2937
COLOR_SUBAYADO = (100 / 255, 116 / 255, 139 / 255)   # #64748b

#: Color con el que se borra el texto original de la plantilla.
COLOR_FONDO = "#ffffff"

#: Margen (en puntos) que se deja al borrar el texto de la plantilla.
MARGEN_BORRADO = 1.5

#: Altura extra (en em) que se cubre sobre el texto cuando hay mayúsculas
#: acentuadas: su tilde sube por encima de la altura de las mayúsculas.
EXTRA_TILDE_EM = 0.16

#: Mayúsculas acentuadas cuyo acento sobresale la altura del texto.
RE_TILDE_MAYUSCULA = re.compile(r"[\u00c1\u00c9\u00cd\u00d3\u00da\u00d1\u00dc]")

#: Marcadores que la plantilla puede declarar para cada valor dinámico.
MARCADORES: Tuple[Tuple[str, "re.Pattern[str]"], ...] = (
    ("dependencia", re.compile(r"<\s*DEPENDENCIA\s*>", re.IGNORECASE)),
    ("otorga", re.compile(r"<\s*PROMEDIO\s*>", re.IGNORECASE)),
    ("nombre", re.compile(r"<\s*NOMBRE\s*>", re.IGNORECASE)),
    ("modalidad", re.compile(r"<\s*CURSO\s*>", re.IGNORECASE)),
    ("evento", re.compile(r"<\s*EVENTO\s*>", re.IGNORECASE)),
    ("fecha", re.compile(r"<\s*FECHA\s*>", re.IGNORECASE)),
)

#: Línea de underscores que precede al bloque de firmas de la plantilla.
RE_LINEA_FIRMA = re.compile(r"^_+$")


# ══════════════════════════════════════════════════════════════════════════
# Lectura de la plantilla
# ══════════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class _Fragmento:
    """Fragmento de texto de la plantilla con su posición en la página."""

    texto: str
    x: float
    y: float
    tamano: float
    ancho: float


@dataclass(frozen=True)
class _Linea:
    """Línea de texto de la plantilla (fragmentos que comparten la misma base)."""

    texto: str
    y: float
    tamano: float
    x_min: float
    x_max: float
    y_min: float
    y_max: float

    @property
    def centro_x(self) -> float:
        """Centro horizontal de la línea (eje del texto centrado)."""
        return (self.x_min + self.x_max) / 2


@dataclass(frozen=True)
class Plantilla:
    """Plantilla PDF de fondo: geometría, textos y contenido original."""

    ruta: str
    ancho: float
    alto: float
    lineas: Tuple[_Linea, ...]
    datos: bytes


def _ancho_fuente(texto: str, fuente: Any, tamano: float) -> float:
    """Ancho de un texto en la fuente incrustada de la plantilla.

    Se usan los anchos reales declarados en el PDF (``/Widths``) para que el
    borrado del texto original abarque exactamente lo que ocupa en la página.
    """
    if fuente is not None:
        try:
            objeto = fuente.get_object() if hasattr(fuente, "get_object") else fuente
            anchos = objeto.get("/Widths")
            primer = objeto.get("/FirstChar")
            if anchos is not None and primer is not None:
                if hasattr(anchos, "get_object"):
                    anchos = anchos.get_object()
                primer = int(primer)
                total = 0.0
                for caracter in texto:
                    try:
                        codigo = caracter.encode("cp1252")[0]
                    except (UnicodeEncodeError, IndexError):
                        codigo = ord(caracter) & 0xFF
                    indice = codigo - primer
                    if 0 <= indice < len(anchos):
                        total += float(anchos[indice])
                    else:
                        total += 500.0
                return total / 1000.0 * tamano
        except Exception:  # pragma: no cover - fuentes con formatos exóticos
            pass
    return stringWidth(texto, "Helvetica", tamano)


def _leer_plantilla(ruta: str | Path) -> Plantilla | None:
    """Lee la plantilla PDF: tamaño de página y posición de sus textos.

    Returns:
        La plantilla interpretada o ``None`` si no se pudo leer.
    """
    if not PPDF_DISPONIBLE:
        return None

    ruta = Path(ruta)
    try:
        datos = ruta.read_bytes()
        lector = PdfReader(io.BytesIO(datos))
        if not lector.pages:
            return None
        pagina = lector.pages[0]
        caja = pagina.mediabox
        ancho, alto = float(caja.width), float(caja.height)

        fragmentos: List[_Fragmento] = []

        def visitante(texto, cm, tm, fuente, tamano_fuente) -> None:
            if not texto or not texto.strip():
                return
            tamano = float(tamano_fuente) or 10.0
            fragmentos.append(
                _Fragmento(
                    texto=texto,
                    x=float(tm[4]),
                    y=float(tm[5]),
                    tamano=tamano,
                    ancho=_ancho_fuente(texto, fuente, tamano),
                )
            )

        pagina.extract_text(visitor_text=visitante)
    except Exception as exc:  # pragma: no cover - depende del archivo
        log.warning("[PDF] No se pudo leer la plantilla '%s': %s", ruta, exc)
        return None

    return Plantilla(
        ruta=str(ruta),
        ancho=ancho,
        alto=alto,
        lineas=_agrupar_lineas(fragmentos),
        datos=datos,
    )


def _agrupar_lineas(fragmentos: Sequence[_Fragmento]) -> Tuple[_Linea, ...]:
    """Agrupa los fragmentos de texto que comparten la misma línea base."""
    grupos: List[List[_Fragmento]] = []
    for fragmento in sorted(fragmentos, key=lambda f: (-f.y, f.x)):
        if grupos and abs(grupos[-1][0].y - fragmento.y) <= 2.0:
            grupos[-1].append(fragmento)
        else:
            grupos.append([fragmento])

    lineas: List[_Linea] = []
    for grupo in grupos:
        tamano = max(f.tamano for f in grupo)
        y = grupo[0].y
        lineas.append(
            _Linea(
                texto=" ".join(f.texto.strip() for f in grupo if f.texto.strip()),
                y=y,
                tamano=tamano,
                x_min=min(f.x for f in grupo),
                x_max=max(f.x + f.ancho for f in grupo),
                y_min=y - 0.22 * tamano,
                y_max=y + 0.78 * tamano,
            )
        )
    return tuple(lineas)


def _anclajes(lineas: Sequence[_Linea]) -> Dict[str, int]:
    """Índice de la línea que ancla cada valor dinámico de la plantilla.

    Los marcadores explícitos (``<NOMBRE>``…) mandan.  Cuando la plantilla no
    los declara, se deduce la posición por el orden fijo del diseño:
    dependencia → otorgamiento → nombre → descripción → evento → modalidad →
    fecha → firmas.
    """
    anclajes: Dict[str, int] = {}
    for clave, patron in MARCADORES:
        for indice, linea in enumerate(lineas):
            if patron.search(linea.texto):
                anclajes[clave] = indice
                break

    if "modalidad" in anclajes:
        indice = anclajes["modalidad"]
        if "evento" not in anclajes and indice > 0:
            anclajes["evento"] = indice - 1
        if "fecha" not in anclajes and indice + 1 < len(lineas):
            anclajes["fecha"] = indice + 1
    if "evento" in anclajes:
        indice = anclajes["evento"]
        if "descripcion" not in anclajes and indice > 0:
            anclajes["descripcion"] = indice - 1
    if "otorga" in anclajes:
        indice = anclajes["otorga"]
        if "dependencia" not in anclajes and indice > 0:
            anclajes["dependencia"] = indice - 1
    return anclajes


def _anclajes_firma(lineas: Sequence[_Linea]) -> Dict[str, int]:
    """Índice de las líneas del bloque de firmas (tras la línea de underscores)."""
    anclajes: Dict[str, int] = {}
    for indice, linea in enumerate(lineas):
        if RE_LINEA_FIRMA.match(linea.texto.strip()):
            for clave, desplazamiento in (
                ("firmante", 1),
                ("cargo", 2),
                ("institucion", 3),
            ):
                if indice + desplazamiento < len(lineas):
                    anclajes[clave] = indice + desplazamiento
            break
    return anclajes


# ══════════════════════════════════════════════════════════════════════════
# Valores dinámicos
# ══════════════════════════════════════════════════════════════════════════
def _normalizar(texto: str) -> str:
    """Compara textos ignorando tildes, mayúsculas y espacios sobrantes."""
    plano = unicodedata.normalize("NFD", str(texto))
    plano = "".join(c for c in plano if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", plano.strip().lower())


def _es_jornada(evento: str) -> bool:
    """True si el evento corresponde a la jornada institucional."""
    texto = str(evento or "").lower()
    return (not texto) or ("incietec" in texto) or ("jornada" in texto)


def _valores_dinamicos(datos: Dict[str, Any]) -> Dict[str, str]:
    """Texto de cada valor dinámico del certificado."""
    rol = str(datos.get("rol", "Participante") or "Participante").strip() or "Participante"
    evento = str(datos.get("evento", "") or "").strip()
    fecha = str(datos.get("fecha", APP_CONFIG.fecha_certificado) or "").strip()
    promedio = datos.get("promedio")
    reconocimiento = datos.get("reconocimiento") or datos.get("mencion")
    curso = datos.get("curso") or datos.get("tipo_participacion")
    ponencia = datos.get("ponencia") or datos.get("conferencia")

    dependencia = str(datos.get("dependencia") or "Facultad de Ingenierías").strip()
    if not dependencia.upper().startswith(("LA ", "EL ")):
        texto_dep = f"LA {dependencia.upper()}"
    else:
        texto_dep = dependencia.upper()

    if promedio:
        texto_otorga = f"OTORGA el {promedio} A:"
    elif reconocimiento:
        texto_otorga = f"OTORGA el {str(reconocimiento).upper()} A:"
    elif rol.lower() in {"asistente", "participante", "asistentes", "participantes"}:
        texto_otorga = "OTORGA el CERTIFICADO DE PARTICIPACIÓN A:"
    else:
        texto_otorga = f"OTORGA el RECONOCIMIENTO COMO {rol.upper()} A:"

    if curso:
        texto_mod = f"Por la MODALIDAD {str(curso).upper()}"
    elif ponencia:
        texto_mod = f"Por la MODALIDAD {rol.upper()}: «{ponencia}»"
    else:
        texto_mod = f"Por la MODALIDAD {rol.upper()}"

    if _es_jornada(evento):
        texto_desc = "Por su gran trabajo en la Jornada Ingenio, Ciencia y Tecnología"
    else:
        texto_desc = "Por su gran trabajo y destacada participación en el evento"

    nombres = str(datos.get("nombres", "") or "").strip()
    apellidos = str(datos.get("apellidos", "") or "").strip()

    return {
        "dependencia": texto_dep,
        "otorga": texto_otorga,
        "nombre": f"{nombres} {apellidos}".strip(),
        "descripcion": texto_desc,
        "evento": evento or "INCIETEC 02-2026",
        "modalidad": texto_mod,
        "fecha": f"Entregado en el Municipio de Caldas, Antioquia – Colombia el día {fecha}",
        "firmante": str(datos.get("firmante_1", "") or "").strip(),
        "cargo": str(datos.get("firmante_cargo", "") or "").strip(),
        "institucion": str(datos.get("firmante_inst", "") or "").strip(),
    }


#: Estilo (fuente y color) de cada bloque según el diseño institucional.
ESTILOS: Dict[str, Tuple[str, str]] = {
    "dependencia": ("Helvetica-Bold", "#074563"),
    "otorga": ("Helvetica-Bold", "#074563"),
    "nombre": ("Helvetica-Bold", "#074563"),
    "descripcion": ("Helvetica", "#1f2937"),
    "evento": ("Helvetica-Bold", "#1f2937"),
    "modalidad": ("Helvetica-Bold", "#074563"),
    "fecha": ("Helvetica", "#1f2937"),
    "firmante": ("Helvetica", "#0f172a"),
    "cargo": ("Helvetica", "#334155"),
    "institucion": ("Helvetica-Bold", "#074563"),
}


# ══════════════════════════════════════════════════════════════════════════
# Dibujo
# ══════════════════════════════════════════════════════════════════════════
def _fuente_negrita() -> str:
    """Nombre de la fuente bold disponible (Helvetica por defecto)."""
    return "Helvetica-Bold"


def _borrar_linea(pdf: canvas.Canvas, linea: _Linea) -> None:
    """Borra el texto original de la plantilla que se va a reemplazar."""
    extra = EXTRA_TILDE_EM * linea.tamano if RE_TILDE_MAYUSCULA.search(linea.texto) else 0.0
    pdf.setFillColor(HexColor(COLOR_FONDO))
    pdf.setStrokeColor(HexColor(COLOR_FONDO))
    pdf.rect(
        linea.x_min - MARGEN_BORRADO,
        linea.y_min - MARGEN_BORRADO,
        (linea.x_max - linea.x_min) + 2 * MARGEN_BORRADO,
        (linea.y_max - linea.y_min) + 2 * MARGEN_BORRADO + extra,
        stroke=0,
        fill=1,
    )


def _dibujar_valor(pdf: canvas.Canvas, texto: str, linea: _Linea, clave: str) -> None:
    """Escribe un valor dinámico sobre la línea que lo ancla."""
    fuente, color = ESTILOS.get(clave, ("Helvetica", "#1f2937"))
    pdf.setFillColor(HexColor(color))
    pdf.setFont(fuente, linea.tamano)
    pdf.drawCentredString(linea.centro_x, linea.y, texto)


def _dibujar_codigo(pdf: canvas.Canvas, codigo: str, ancho: float, alto: float) -> None:
    """Código de verificación en la esquina inferior izquierda."""
    if not codigo:
        return
    pdf.setFont("Helvetica", 8)
    pdf.setFillColor(HexColor("#64748b"))
    pdf.drawString(40, min(25, alto - 20), f"Código: {codigo}")


def _componer_plantilla(
    plantilla: Plantilla,
    datos: Dict[str, Any],
) -> bytes:
    """Genera la capa de texto dinámico sobre la plantilla.

    Returns:
        Los bytes de un PDF con el tamaño de página de la plantilla.
    """
    lineas = plantilla.lineas
    anclajes = _anclajes(lineas)
    if not anclajes:
        raise ValueError("La plantilla no declara marcadores dinámicos")

    valores = _valores_dinamicos(datos)
    firma = _anclajes_firma(lineas)

    # Valores a escribir y línea que los ancla.
    pendientes: List[Tuple[str, int]] = []
    for clave, indice in anclajes.items():
        texto = valores.get(clave, "")
        if not texto:
            continue
        if clave == "descripcion" and _normalizar(texto) == _normalizar(lineas[indice].texto):
            continue  # el texto de la plantilla ya es el correcto
        pendientes.append((clave, indice))
    for clave, indice in firma.items():
        if valores.get(clave):
            pendientes.append((clave, indice))

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=(plantilla.ancho, plantilla.alto))

    for _, indice in pendientes:
        _borrar_linea(pdf, lineas[indice])

    for clave, indice in pendientes:
        _dibujar_valor(pdf, valores[clave], lineas[indice], clave)

    _dibujar_codigo(pdf, str(datos.get("codigo", "") or ""), plantilla.ancho, plantilla.alto)

    pdf.save()
    return buffer.getvalue()


def _fusionar(plantilla: Plantilla, superposicion: bytes, salida: Path, clave: str | None) -> None:
    """Compone la plantilla con la capa de texto y escribe el PDF final."""
    lector = PdfReader(io.BytesIO(plantilla.datos))
    encima = PdfReader(io.BytesIO(superposicion)).pages[0]

    escritor = PdfWriter()
    escritor.add_page(lector.pages[0])
    escritor.pages[0].merge_page(encima)
    if clave:
        escritor.encrypt(clave, "lasalle-unilasallista")

    with salida.open("wb") as archivo:
        escritor.write(archivo)


# ══════════════════════════════════════════════════════════════════════════
# Diseño propio (respaldo cuando no hay plantilla utilizable)
# ══════════════════════════════════════════════════════════════════════════
def _dibujar_estrella(pdf: canvas.Canvas, cx: float, cy: float, radio: float, color: Any) -> None:
    p = pdf.beginPath()
    for i in range(10):
        r = radio if i % 2 == 0 else radio * 0.45
        ang = -math.pi / 2 + i * math.pi / 5
        x = cx + r * math.cos(ang)
        y = cy + r * math.sin(ang)
        if i == 0:
            p.moveTo(x, y)
        else:
            p.lineTo(x, y)
    p.close()
    pdf.setFillColor(color)
    pdf.drawPath(p, stroke=0, fill=1)


def _dibujar_fondo_por_defecto(pdf: canvas.Canvas, ancho: float, alto: float) -> None:
    """Diseño corporativo oficial de la Corporación Universitaria Lasallista."""
    _dibujar_fondo_unilasallista(pdf, ancho, alto)


def _dibujar_fondo_unilasallista(pdf: canvas.Canvas, ancho: float, alto: float) -> None:
    """Diseño corporativo oficial de la Corporación Universitaria Lasallista."""
    # 1. Fondo blanco limpio
    pdf.setFillColor(HexColor("#ffffff"))
    pdf.rect(0, 0, ancho, alto, stroke=0, fill=1)

    # 2. Onda decorativa superior izquierda (esquina)
    p_cian = pdf.beginPath()
    p_cian.moveTo(0, alto)
    p_cian.lineTo(150, alto)
    p_cian.curveTo(120, alto - 50, 45, alto - 85, 0, alto - 100)
    p_cian.close()
    pdf.setFillColor(HexColor("#00a3e0"))
    pdf.drawPath(p_cian, stroke=0, fill=1)

    p_cian2 = pdf.beginPath()
    p_cian2.moveTo(0, alto - 30)
    p_cian2.lineTo(90, alto)
    p_cian2.lineTo(140, alto)
    p_cian2.curveTo(80, alto - 40, 20, alto - 70, 0, alto - 90)
    p_cian2.close()
    pdf.setFillColor(HexColor("#38c6f4"))
    pdf.drawPath(p_cian2, stroke=0, fill=1)

    p_naranja = pdf.beginPath()
    p_naranja.moveTo(0, alto)
    p_naranja.lineTo(110, alto)
    p_naranja.curveTo(75, alto - 45, 20, alto - 80, 0, alto - 95)
    p_naranja.close()
    pdf.setFillColor(HexColor("#e84e1b"))
    pdf.drawPath(p_naranja, stroke=0, fill=1)

    p_amarillo = pdf.beginPath()
    p_amarillo.moveTo(0, alto)
    p_amarillo.lineTo(75, alto)
    p_amarillo.curveTo(45, alto - 45, 10, alto - 75, 0, alto - 85)
    p_amarillo.close()
    pdf.setFillColor(HexColor("#fdb813"))
    pdf.drawPath(p_amarillo, stroke=0, fill=1)

    # Trazos sutiles en la onda
    pdf.setStrokeColor(HexColor("#ffffff"))
    pdf.setLineWidth(1)
    pdf.line(0, alto - 40, 60, alto)
    pdf.line(0, alto - 65, 100, alto)

    # 3. Logos superiores derechos
    x_base = ancho - 440
    y_logo = alto - 48

    # SOMOS LA SALLE
    pdf.setFillColor(HexColor("#074563"))
    pdf.setFont("Helvetica-Bold", 15)
    pdf.drawString(x_base, y_logo + 12, "SOMOS")
    pdf.drawString(x_base, y_logo - 3, "LA SALLE")

    # Separador 1
    pdf.setStrokeColor(HexColor("#074563"))
    pdf.setLineWidth(1)
    pdf.line(x_base + 80, y_logo - 6, x_base + 80, y_logo + 24)

    # Unilasallista Corporación Universitaria ★
    x_u = x_base + 92
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(x_u, y_logo + 5, "Unilasallista")
    _dibujar_estrella(pdf, x_u + 115, y_logo + 13, 8.5, HexColor("#074563"))

    pdf.setFont("Helvetica", 8)
    pdf.drawString(x_u + 12, y_logo - 6, "Corporación Universitaria")

    # Separador 2
    pdf.setStrokeColor(HexColor("#074563"))
    pdf.setLineWidth(1)
    pdf.line(x_u + 136, y_logo - 6, x_u + 136, y_logo + 24)

    # Acreditada en Alta Calidad
    x_ac = x_u + 148
    pdf.setFont("Helvetica", 12)
    pdf.drawString(x_ac, y_logo + 9, "Acreditada en")
    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(x_ac, y_logo - 3, "Alta Calidad")

    pdf.setFont("Helvetica", 4.8)
    pdf.setFillColor(HexColor("#334155"))
    pdf.drawString(x_ac, y_logo - 11, "Por 6 años, con resolución 007577 del 20 de mayo de 2024")
    pdf.drawString(x_ac + 8, y_logo - 17, "En lugar de desarrollo Caldas, Antioquia")

    # 4. Encabezados institucionales
    pdf.setFillColor(HexColor("#074563"))
    pdf.setFont("Helvetica-Bold", 17)
    pdf.drawCentredString(ancho / 2, alto - 105, "CORPORACIÓN UNIVERSITARIA LASALLISTA")

    pdf.setFillColor(HexColor("#1e3a4c"))
    pdf.setFont("Helvetica-Bold", 7.2)
    pdf.drawCentredString(
        ancho / 2, alto - 122,
        "CON PERSONERÍA JURÍDICA RECONOCIDA MEDIANTE RESOLUCIÓN 9887 DE 1983, EXPEDIDA POR EL MINISTERIO DE EDUCACIÓN NACIONAL DE COLOMBIA",
    )

    # 5. Badge inferior derecho
    badge_x = ancho - 260
    badge_y = 20
    badge_w = 230
    badge_h = 36
    pdf.setFillColor(HexColor("#102a45"))
    pdf.roundRect(badge_x, badge_y, badge_w, badge_h, 7, stroke=0, fill=1)

    pdf.setFillColor(HexColor("#00b5e2"))
    pdf.roundRect(badge_x + 9, badge_y + 4.5, 3.5, badge_h - 9, 1.5, stroke=0, fill=1)

    pdf.setFont("Helvetica", 7.5)
    pdf.setFillColor(HexColor("#94a3b8"))
    pdf.drawString(badge_x + 20, badge_y + 20.5, "Vigilada Mineducación")

    pdf.setFont("Helvetica-Bold", 10.5)
    pdf.setFillColor(HexColor("#ffffff"))
    pdf.drawString(badge_x + 20, badge_y + 8, "www.unilasallista.edu.co")


def _generar_diseno_propio(
    datos: Dict[str, Any],
    salida: Path,
    clave: str | None,
    fondo: str | None = None,
) -> None:
    """Genera el certificado con el diseño dibujado por reportlab."""
    ancho, alto = landscape(A4)

    valores = _valores_dinamicos(datos)
    nombre = valores["nombre"]
    rol = str(datos.get("rol", "Participante") or "Participante")

    opciones: Dict[str, Any] = {"pagesize": landscape(A4)}
    if clave:
        opciones["encrypt"] = (clave, "lasalle-unilasallista")

    pdf = canvas.Canvas(str(salida), **opciones)

    # ── 1. Fondo institucional ────────────────────────────────────────────
    if fondo and Path(fondo).exists():
        try:
            from reportlab.lib.utils import ImageReader

            pdf.drawImage(
                ImageReader(fondo), 0, 0, width=ancho, height=alto,
                preserveAspectRatio=True, anchor="c", mask="auto",
            )
        except Exception:  # pragma: no cover - depende del recurso
            pass
    if not (fondo and Path(fondo).exists()):
        _dibujar_fondo_unilasallista(pdf, ancho, alto)

    # ── 2. Dependencia ────────────────────────────────────────────────────
    pdf.setFillColor(HexColor("#074563"))
    pdf.setFont(_fuente_negrita(), 15)
    pdf.drawCentredString(ancho / 2, alto - 156, valores["dependencia"])

    # ── 3. Otorgamiento ───────────────────────────────────────────────────
    pdf.setFont(_fuente_negrita(), 12)
    pdf.drawCentredString(ancho / 2, alto - 194, valores["otorga"])

    # ── 4. Nombre del participante ────────────────────────────────────────
    pdf.setFont("Helvetica-BoldOblique", 27)
    pdf.drawCentredString(ancho / 2, alto - 245, nombre)

    # ── 5. Texto descriptivo / Evento ─────────────────────────────────────
    pdf.setFillColor(HexColor("#1f2937"))
    pdf.setFont("Helvetica", 11.5)
    pdf.drawCentredString(ancho / 2, alto - 295, valores["descripcion"])
    pdf.setFont(_fuente_negrita(), 11.5)
    pdf.drawCentredString(ancho / 2, alto - 313, valores["evento"])

    # ── 6. Modalidad / Rol / Ponencia ─────────────────────────────────────
    pdf.setFillColor(HexColor("#074563"))
    pdf.setFont(_fuente_negrita(), 11)
    pdf.drawCentredString(ancho / 2, alto - 350, valores["modalidad"])

    # ── 7. Fecha y Lugar ──────────────────────────────────────────────────
    pdf.setFillColor(HexColor("#1f2937"))
    pdf.setFont("Helvetica", 10.5)
    pdf.drawCentredString(ancho / 2, alto - 380, valores["fecha"])

    # ── 8. Firma ──────────────────────────────────────────────────────────
    firmante = datos.get("firmante_1") or "Álvaro Arango Ruiz"
    cargo = datos.get("firmante_cargo") or f"Decano {str(datos.get('dependencia') or 'Facultad de Ingenierías')}"
    institucion = datos.get("firmante_inst") or "Unilasallista"

    pdf.setStrokeColor(HexColor("#64748b"))
    pdf.setLineWidth(0.8)
    pdf.line(ancho / 2 - 95, 125, ancho / 2 + 95, 125)

    pdf.setFillColor(HexColor("#0f172a"))
    pdf.setFont("Helvetica", 10.5)
    pdf.drawCentredString(ancho / 2, 110, str(firmante))

    pdf.setFillColor(HexColor("#334155"))
    pdf.setFont("Helvetica", 9.5)
    pdf.drawCentredString(ancho / 2, 96, str(cargo))

    pdf.setFillColor(HexColor("#074563"))
    pdf.setFont(_fuente_negrita(), 9.5)
    pdf.drawCentredString(ancho / 2, 82, str(institucion))

    # ── 9. Código de verificación ─────────────────────────────────────────
    _dibujar_codigo(pdf, str(datos.get("codigo", "") or ""), ancho, alto)

    pdf.save()


# ══════════════════════════════════════════════════════════════════════════
# API pública
# ══════════════════════════════════════════════════════════════════════════
def _resolver_plantilla(plantilla: str | Path | None) -> str | None:
    """Ruta de la plantilla a usar, si el archivo existe."""
    if not plantilla:
        return None
    ruta = Path(plantilla)
    return str(ruta) if ruta.is_file() else None


def generar_certificado(
    datos: Dict[str, Any],
    plantilla: str | None = None,
    salida: str | Path | None = None,
    proteger: bool | None = None,
) -> str:
    """Genera un certificado PDF personalizado.

    Args:
        datos: ``{nombres, apellidos, rol, evento, fecha, ...}`` — puede
            incluir ``ponencia``, ``conferencia``, ``documento``, ``codigo``,
            ``curso``, ``promedio`` y las claves ``firmante_1`` /
            ``firmante_2``.
        plantilla: Ruta del PDF de fondo.  Si el archivo existe se usa como
            página base y el texto dinámico se coloca sobre sus marcadores.
            Si no existe (o no declara marcadores) se dibuja el diseño
            propio por defecto.
        salida: Ruta del PDF a generar. Si se omite se deriva del nombre.
        proteger: Cifra el PDF con el número de documento como contraseña.

    Returns:
        Ruta del PDF generado.
    """
    if proteger is None:
        proteger = APP_CONFIG.proteger_pdf

    nombres = str(datos.get("nombres", "")).strip()
    apellidos = str(datos.get("apellidos", "")).strip()
    nombre_completo = f"{nombres} {apellidos}".strip()

    if salida is None:
        base = "".join(c if c.isalnum() else "_" for c in nombre_completo) or "certificado"
        salida = APP_CONFIG.dir_salida / f"{base}.pdf"
    salida = Path(salida)
    salida.parent.mkdir(parents=True, exist_ok=True)

    # Contraseña del PDF: documento del participante o código de evento.
    documento = str(datos.get("documento", "") or "")
    clave = documento or str(datos.get("codigo", "") or "")
    clave = clave if proteger else None

    ruta_plantilla = _resolver_plantilla(plantilla)
    if ruta_plantilla is not None:
        info = _leer_plantilla(ruta_plantilla)
        if info is not None:
            try:
                superposicion = _componer_plantilla(info, datos)
                _fusionar(info, superposicion, salida, clave)
                log.info(
                    "[PDF] Certificado con la plantilla '%s': %s",
                    Path(ruta_plantilla).name, salida.name,
                )
                return str(salida)
            except Exception as exc:
                log.warning(
                    "[PDF] No se pudo usar la plantilla '%s' (%s); "
                    "se genera el diseño propio.",
                    ruta_plantilla, exc,
                )

    _generar_diseno_propio(datos, salida, clave)
    log.info("[PDF] Generando certificado: %s", salida.name)
    return str(salida)


def generar_certificados(
    participantes: List[Dict[str, Any]],
    plantilla: str | None,
    directorio_salida: str | Path | None = None,
    proteger: bool | None = None,
) -> List[Dict[str, Any]]:
    """Genera un PDF por participante.

    Returns:
        Lista de ``{"correo", "nombre", "ruta", "estado", "detalle"}``.
    """
    directorio = Path(directorio_salida or APP_CONFIG.dir_salida)
    directorio.mkdir(parents=True, exist_ok=True)

    resultados: List[Dict[str, Any]] = []
    for participante in participantes:
        correo = str(participante.get("correo", "")).strip() or "sin_correo"
        seguro = "".join(c if c.isalnum() or c in "-_." else "_" for c in correo)
        ruta = directorio / f"{seguro}.pdf"
        try:
            generada = generar_certificado(
                participante, plantilla=plantilla, salida=ruta, proteger=proteger
            )
            resultados.append(
                {
                    "correo": correo,
                    "nombre": f"{participante.get('nombres', '')} "
                    f"{participante.get('apellidos', '')}".strip(),
                    "ruta": generada,
                    "estado": "OK",
                    "detalle": "",
                }
            )
        except Exception as exc:
            log.exception("[PDF] Error al generar el certificado de %s", correo)
            resultados.append(
                {
                    "correo": correo,
                    "nombre": "",
                    "ruta": "",
                    "estado": "ERROR",
                    "detalle": str(exc),
                }
            )
    return resultados
