"""Genera los recursos estáticos del proyecto.

Ejecución::

    python tools/generar_recursos.py

Produce:
  * ``static/logo_unilasalle.png``      — logotipo institucional.
  * ``templates/certificado_base.pdf``  — plantilla base del certificado.
  * ``data/ejemplo_evento.xlsx``         — libro de ejemplo con las 5 hojas.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from reportlab.lib.colors import HexColor  # noqa: E402
from reportlab.lib.pagesizes import A4, landscape  # noqa: E402
from reportlab.pdfgen import canvas  # noqa: E402

from config import APP_CONFIG  # noqa: E402

VERDE = (0.0, 0.4, 0.28)
GRIS = (0.35, 0.35, 0.35)

#: Versión entera (RGBA) para Pillow.
VERDE_RGBA = (0, 102, 71, 255)
GRIS_RGBA = (89, 89, 89, 255)
BLANCO_RGBA = (255, 255, 255, 255)


# ══════════════════════════════════════════════════════════════════════════
# Logotipo
# ══════════════════════════════════════════════════════════════════════════
def generar_logo(destino: Path, ancho: int = 520, alto: int = 300) -> Path:
    """Dibuja el logotipo institucional con Pillow."""
    from PIL import Image, ImageDraw, ImageFont

    imagen = Image.new("RGBA", (ancho, alto), (255, 255, 255, 0))
    dibujo = ImageDraw.Draw(imagen)

    def fuente(tamano: int, negrita: bool = False):
        candidatos = [
            Path("C:/Windows/Fonts/arialbd.ttf" if negrita else "C:/Windows/Fonts/arial.ttf"),
            Path("C:/Windows/Fonts/segoeuib.ttf" if negrita else "C:/Windows/Fonts/segoeui.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if negrita
                 else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        ]
        for ruta in candidatos:
            if ruta.exists():
                try:
                    return ImageFont.truetype(str(ruta), tamano)
                except OSError:  # pragma: no cover
                    continue
        return ImageFont.load_default()

    # Escudo institucional
    escudo = [
        (ancho // 2, 18),
        (ancho // 2 + 92, 52),
        (ancho // 2 + 92, 130),
        (ancho // 2, 196),
        (ancho // 2 - 92, 130),
        (ancho // 2 - 92, 52),
    ]
    dibujo.polygon(escudo, fill=VERDE_RGBA, outline=BLANCO_RGBA, width=4)

    # Elementos gráficos del escudo (dos trazos diagonales)
    dibujo.polygon(
        [(ancho // 2 - 34, 60), (ancho // 2 + 10, 60), (ancho // 2 - 6, 110),
         (ancho // 2 + 38, 110)],
        fill=BLANCO_RGBA,
    )
    dibujo.polygon(
        [(ancho // 2 - 44, 120), (ancho // 2 + 20, 120), (ancho // 2 + 4, 168),
         (ancho // 2 - 60, 168)],
        fill=BLANCO_RGBA,
    )

    # Marca de la "U" (La Salle)
    fuente_u = fuente(64, negrita=True)
    dibujo.text((ancho // 2, 150), "U", font=fuente_u, fill=BLANCO_RGBA, anchor="mm")

    # Wordmark
    fuente_titulo = fuente(38, negrita=True)
    fuente_sub = fuente(20)
    dibujo.text(
        (ancho // 2, 226), "UNIVERSIDAD DE LA SALLE",
        font=fuente_titulo, fill=VERDE_RGBA, anchor="mm",
    )
    dibujo.text(
        (ancho // 2, 262), "Motor para el Desarrollo Integral",
        font=fuente_sub, fill=GRIS_RGBA, anchor="mm",
    )

    destino.parent.mkdir(parents=True, exist_ok=True)
    imagen.save(destino, "PNG")
    return destino


# ══════════════════════════════════════════════════════════════════════════
# Plantilla base del certificado
# ══════════════════════════════════════════════════════════════════════════
def _dibujar_estrella(pdf: canvas.Canvas, cx: float, cy: float, radio: float, color: HexColor) -> None:
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


def generar_plantilla_base(destino: Path) -> Path:
    """Crea la plantilla institucional usada como fondo de los certificados (estilo Unilasallista)."""
    ancho, alto = landscape(A4)
    pdf = canvas.Canvas(str(destino), pagesize=landscape(A4))

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

    pdf.setFillColor(HexColor("#074563"))
    pdf.setFont("Helvetica-Bold", 15)
    pdf.drawCentredString(ancho / 2, alto - 156, "LA FACULTAD DE INGENIERÍAS")

    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawCentredString(ancho / 2, alto - 194, "OTORGA el <PROMEDIO> A:")

    # Placeholder <NOMBRE>
    pdf.setFont("Helvetica-BoldOblique", 27)
    pdf.drawCentredString(ancho / 2, alto - 245, "<NOMBRE>")

    # Textos descriptivos de ejemplo
    pdf.setFillColor(HexColor("#1f2937"))
    pdf.setFont("Helvetica", 11.5)
    pdf.drawCentredString(ancho / 2, alto - 295, "Por su gran trabajo en la Jornada Ingenio, Ciencia y Tecnología")
    pdf.setFont("Helvetica-Bold", 11.5)
    pdf.drawCentredString(ancho / 2, alto - 313, "INCIETEC 02-2026")

    pdf.setFillColor(HexColor("#074563"))
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawCentredString(ancho / 2, alto - 350, "Por la MODALIDAD <CURSO>")

    pdf.setFillColor(HexColor("#1f2937"))
    pdf.setFont("Helvetica", 10.5)
    pdf.drawCentredString(ancho / 2, alto - 380, "Entregado en el Municipio de Caldas, Antioquia – Colombia el día 13 de noviembre del 2026")

    # 5. Firma
    pdf.setStrokeColor(HexColor("#64748b"))
    pdf.setLineWidth(0.8)
    pdf.line(ancho / 2 - 95, 125, ancho / 2 + 95, 125)

    pdf.setFillColor(HexColor("#0f172a"))
    pdf.setFont("Helvetica", 10.5)
    pdf.drawCentredString(ancho / 2, 110, "Álvaro Arango Ruiz")

    pdf.setFillColor(HexColor("#334155"))
    pdf.setFont("Helvetica", 9.5)
    pdf.drawCentredString(ancho / 2, 96, "Decano Facultad de Ingenierías")

    pdf.setFillColor(HexColor("#074563"))
    pdf.setFont("Helvetica-Bold", 9.5)
    pdf.drawCentredString(ancho / 2, 82, "Unilasallista")

    # 6. Badge inferior derecho
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

    pdf.save()
    return destino


# ══════════════════════════════════════════════════════════════════════════
# Libro de ejemplo
# ══════════════════════════════════════════════════════════════════════════
def generar_excel_ejemplo(destino: Path) -> Path:
    """Crea el libro de ejemplo con las cinco hojas y casos borde."""
    import pandas as pd

    asistentes = pd.DataFrame(
        {
            "nombres": [
                "maria jose", "JUAN", "ana maría", "carlos", "luisa fernanda",
                "  pedro   pablo  ", "", "sofía",
            ],
            "apellidos": [
                "pérez", "DE LA CRUZ gómez", "garcía lópez", "quintero", "rojas",
                "osorio", "castillo", "beltrán",
            ],
            "correo": [
                "maria.perez@correo.com", "juan.cruz@correo.com",
                "ana.garcia@correo.com", "carlos.quintero@correo.com",
                "luisa.rojas@correo.com", "pedro.osorio@correo.com",
                "sin.dominio@", "sofia.beltran@correo.com",
            ],
            "tipo_participacion": [
                "Asistente", "Asistente", "Asistente", "Asistente",
                "Asistente", "Asistente", "Asistente", "Asistente",
            ],
        }
    )

    ponentes = pd.DataFrame(
        {
            # Encabezados alternativos: el mapeo semántico de IA los normaliza.
            "Nombre Completo": [
                "camila andrés", "diego fernando", "valentina",
            ],
            "Apellidos": ["ruiz pineda", "hernández", "soto mendoza"],
            "Email": [
                "camila.ruiz@correo.com", "diego.hernandez@correo.com",
                "valentina.soto@correo.com",
            ],
            "Cédula": ["1010101010", "2020202020", "3030303030"],
            "Ponencia": [
                "Aplicaciones de PLN en la educación superior",
                "Detección de duplicados con similitud fuzzy",
                "Certificados digitales para eventos académicos",
            ],
        }
    )

    conferenciantes = pd.DataFrame(
        {
            "nombres": ["ricardo", "MÓNICA"],
            "apellidos": ["alvarez", "ospina"],
            "correo": ["ricardo.alvarez@correo.com", "monica.ospina@correo.com"],
            "documento": ["4040404040", "5050505050"],
            "conferencia": [
                "Ética de la inteligencia artificial en la universidad",
                "Protección de datos personales y certificación digital",
            ],
        }
    )

    evaluadores = pd.DataFrame(
        {
            "nombres": ["laura", "andrés"],
            "apellidos": ["mendoza", "cárdenas"],
            "correo": ["laura.mendoza@correo.com", "andres.cardenas@correo.com"],
            "documento": ["6060606060", "7070707070"],
            "area": ["Inteligencia Artificial", "Ciencia de Datos"],
            "comite": ["Comité Académico", "Comité Académico"],
        }
    )

    organizadores = pd.DataFrame(
        {
            "nombres": ["gabriela", "julián"],
            "apellidos": ["navarro", "ortega"],
            "correo": ["gabriela.navarro@correo.com", "julian.ortega@correo.com"],
            "cargo": ["Coordinadora del evento", "Director del programa"],
        }
    )

    destino.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(destino, engine="openpyxl") as escritor:
        asistentes.to_excel(escritor, sheet_name="Asistentes", index=False)
        ponentes.to_excel(escritor, sheet_name="Ponentes", index=False)
        conferenciantes.to_excel(escritor, sheet_name="Conferenciantes", index=False)
        evaluadores.to_excel(escritor, sheet_name="Evaluadores", index=False)
        organizadores.to_excel(escritor, sheet_name="Organizadores", index=False)

    return destino


def main() -> None:
    logo = generar_logo(APP_CONFIG.dir_estaticos / "logo_unilasalle.png")
    destino_plantilla = APP_CONFIG.dir_plantillas / "certificado_base.pdf"
    if destino_plantilla.exists():
        # La plantilla institucional es un recurso editable: nunca se pisa.
        plantilla = destino_plantilla
        print(f"[OK] Plantilla:     {plantilla} (se conserva la existente)")
    else:
        plantilla = generar_plantilla_base(destino_plantilla)
        print(f"[OK] Plantilla:     {plantilla}")
    excel = generar_excel_ejemplo(APP_CONFIG.dir_datos / "ejemplo_evento.xlsx")

    print(f"[OK] Logotipo:      {logo}")
    print(f"[OK] Excel ejemplo: {excel}")


if __name__ == "__main__":
    main()
