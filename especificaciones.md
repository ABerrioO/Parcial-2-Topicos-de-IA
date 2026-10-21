# 🎓 Certificado Unilasallista

**Proyecto aplicado — Tópicos de Inteligencia Artificial**
Universidad de La Salle · Octubre 2026 (2026-II)
*Parcial · Propuesta Técnica y Prototipo Funcional*

---

## Tabla de contenido

1. [Resumen ejecutivo](#1-resumen-ejecutivo)
2. [Propuesta técnica](#2-propuesta-técnica)
3. [Arquitectura tecnológica](#3-arquitectura-tecnológica)
4. [Servicio de correo](#4-investigación-y-justificación-del-servicio-de-correo)
5. [Prototipo funcional](#5-prototipo-funcional)
6. [Aplicación de tópicos de IA](#6-aplicación-de-tópicos-de-inteligencia-artificial)
7. [Informe de pruebas](#7-informe-de-pruebas)
8. [Seguridad y protección de datos](#8-seguridad-y-protección-de-datos)
9. [Sustentación y reflexión final](#9-sustentación-y-reflexión-final)

---

## 1. Resumen ejecutivo

**Certificado Unilasallista** es un módulo que automatiza la generación y el envío de certificados académicos para eventos institucionales. Cualquier dependencia universitaria puede gestionar eventos, cargar participantes desde Excel, asociar plantillas personalizadas y enviar los certificados por correo de forma segura, trazable y reutilizable.

La solución combina:

- **Procesamiento de datos:** `pandas`, `openpyxl`
- **Generación de PDF:** `reportlab`
- **Envío de correos:** `smtplib`
- **IA aplicada:** normalización de nombres con PLN, detección de duplicados por similitud, validación semántica de encabezados y generación asistida de mensajes.

> **Valor institucional:** reduce tiempos operativos, elimina errores manuales, garantiza trazabilidad de envíos y protege los datos personales de la comunidad lasallista.

---

## 2. Propuesta técnica

### 2.1 Descripción del problema

Hoy las dependencias gestionan los certificados de forma manual o con herramientas dispersas (Excel + Word + correo individual), lo que genera:

- Alto consumo de tiempo en eventos con más de 50 participantes.
- Riesgo de errores en nombres, correos o roles.
- Dificultad de trazabilidad y auditoría de envíos.
- Duplicación accidental de certificados.
- Falta de reutilización entre dependencias.

### 2.2 Solución planteada

Una **aplicación web modular en Python** que centraliza todo el flujo:

```
Carga Excel → Validación IA → Plantilla → Generar PDF → Envío SMTP → Registro
```

El sistema es multi-dependencia y multi-evento.

| Capacidad | Descripción |
|---|---|
| 📊 Carga inteligente | Lee Excel con 5 hojas (Asistentes, Ponentes, Conferenciantes, Evaluadores, Organizadores). |
| 🤖 Validación con IA | Normaliza nombres, detecta duplicados y valida encabezados mediante PLN y similitud. |
| 📜 Generación PDF | Certificados personalizados desde plantillas con datos dinámicos. |
| 📧 Envío SMTP | Servidor institucional autorizado con autenticación segura. |
| 🔒 Seguridad | Credenciales en variables de entorno, PDFs con contraseña y cifrado TLS. |
| 📈 Trazabilidad | Registro de envíos exitosos, fallidos y pendientes en SQLite. |

### 2.3 Requerimientos funcionales cubiertos

| RF | Descripción | Estado |
|---|---|---|
| RF1 | Carga de Excel con 5 hojas de participantes | ✅ Implementado |
| RF2 | Identificación y validación de campos | ✅ Implementado |
| RF3 | Configuración de plantilla de certificado | ✅ Implementado |
| RF4 | Configuración del servicio SMTP | ✅ Implementado |
| RF5 | Automatización del envío | ✅ Implementado |
| RF6 | Control y trazabilidad de envíos | ✅ Implementado |
| RF7 | Reutilización multi-dependencia | ✅ Implementado |

---

## 3. Arquitectura tecnológica

### 3.1 Stack seleccionado

| Tecnología | Rol | Justificación |
|---|---|---|
| **Python 3.11** | Lenguaje principal | Robusto, con amplio ecosistema para IA, datos y automatización. |
| **Flask** | Framework web | Ligero, ideal para prototipos modulares desplegables en servidores institucionales. |
| **pandas + openpyxl** | Procesamiento Excel | Lectura eficiente de archivos con múltiples hojas. |
| **reportlab** | Generación PDF | Certificados con texto, imágenes y firmas. |
| **smtplib** | Envío de correos | Integración nativa con SMTP institucional vía TLS/SSL. |
| **spaCy / fuzzywuzzy** | IA aplicada | Normalización de nombres, duplicados y similitud. |
| **SQLite** | Base de datos | Eventos, participantes y trazabilidad. |
| **python-dotenv** | Credenciales | SMTP fuera del código fuente. |

### 3.2 Diagrama de arquitectura

```
┌─────────────┐    ┌──────────────┐    ┌─────────────────────────┐    ┌──────────┐
│ Dependencia │───▶│ Flask Web App│───▶│ Módulo IA (PLN)         │───▶│          │
│  (Usuario)  │    │ API REST + UI│    │ Normalización+Duplicados│    │          │
└─────────────┘    │              │    ├─────────────────────────┤    │  SQLite  │
                   │              │───▶│ Generador PDF (reportlab)│───▶│Trazabili-│
                   │              │    ├─────────────────────────┤    │   dad    │
                   │              │───▶│ Servicio SMTP (TLS+Auth)│───▶│          │
                   └──────────────┘    └─────────────────────────┘    └──────────┘
```

### 3.3 Flujo del proceso

`1. Carga Excel` → `2. Validación IA` → `3. Plantilla` → `4. Generar PDF` → `5. Envío SMTP` → `6. Registro`

---

## 4. Investigación y justificación del servicio de correo

### 4.1 Alternativas evaluadas

| Servicio | Ventajas | Desventajas | Viabilidad |
|---|---|---|---|
| **SMTP Institucional** (Office 365 / Gmail corporativo) | Dominio oficial `@lasalle.edu.co`; costo cero; reconocimiento institucional; cumple políticas de datos | Límite ~2000 envíos/día; requiere MFA; configuración inicial con TI | ⭐ **Recomendado** |
| **SendGrid** (API) | Alto volumen; analíticas avanzadas; plantillas dinámicas | Costo mensual; dominio externo; requiere contrato | Secundario |
| **Mailgun** | API robusta; validación de correos | Costo; curva de aprendizaje | Alternativa |
| **AWS SES** | Muy económico a escala; alta deliverability | Complejidad de infraestructura; requiere cuenta AWS institucional | Futuro |

### 4.2 Recomendación final

Se recomienda el **SMTP Institucional (Office 365)** porque:

- **Costo cero:** ya contratado por la universidad.
- **Identidad institucional:** los certificados llegan desde `@lasalle.edu.co`.
- **Cumplimiento normativo:** los datos permanecen en infraestructura autorizada.
- **Volumen suficiente:** 2000 envíos/día cubre la mayoría de eventos académicos.
- **Seguridad:** autenticación OAuth2 + TLS + MFA.

Para eventos masivos (>1500 participantes) se puede escalar a SendGrid manteniendo la arquitectura mediante un adaptador de servicio de correo.

### 4.3 Configuración SMTP propuesta

```ini
# .env (NO subir al repositorio)
SMTP_HOST=smtp.office365.com
SMTP_PORT=587
SMTP_USER=certificados@lasalle.edu.co
SMTP_PASS=${SECRET_FROM_KEYVAULT}
SMTP_USE_TLS=True
SMTP_FROM_NAME=Certificados Unilasallista
```

> ⚠️ **Seguridad:** las credenciales nunca se incluyen en el código fuente. Se gestionan mediante variables de entorno o un gestor de secretos (Azure Key Vault / AWS Secrets Manager).

---

## 5. Prototipo funcional

### 5.1 Estructura del proyecto

```
certificado-unilasallista/
├── app.py                    # Punto de entrada Flask
├── config.py                 # Configuración general
├── .env                      # Variables de entorno (no versionado)
├── requirements.txt
├── modules/
│   ├── __init__.py
│   ├── excel_loader.py       # Carga y validación de Excel
│   ├── ia_validator.py       # Módulo IA (PLN + duplicados)
│   ├── pdf_generator.py      # Generación de certificados
│   ├── mail_service.py       # Envío SMTP
│   └── tracker.py            # Trazabilidad SQLite
├── templates/
│   ├── certificado_base.pdf  # Plantilla institucional
│   └── index.html
├── static/
│   └── logo_unilasalle.png
├── data/
│   └── ejemplo_evento.xlsx
└── tests/
    └── test_flujo.py
```

### 5.2 Carga y validación de Excel — `modules/excel_loader.py`

```python
import pandas as pd
from typing import Dict, List

HOJAS_REQUERIDAS = ['Asistentes', 'Ponentes', 'Conferenciantes',
                    'Evaluadores', 'Organizadores']

CAMPOS_POR_ROL = {
    'Asistentes':     ['nombres', 'apellidos', 'correo'],
    'Ponentes':       ['nombres', 'apellidos', 'correo', 'documento', 'ponencia'],
    'Conferenciantes':['nombres', 'apellidos', 'correo', 'documento', 'conferencia'],
    'Evaluadores':    ['nombres', 'apellidos', 'correo', 'documento'],
    'Organizadores':  ['nombres', 'apellidos', 'correo'],
}

def cargar_excel(ruta: str) -> Dict[str, pd.DataFrame]:
    """Carga un archivo Excel y devuelve un diccionario por hoja."""
    xls = pd.ExcelFile(ruta)
    hojas_existentes = [h for h in xls.sheet_names if h in HOJAS_REQUERIDAS]
    if len(hojas_existentes) != len(HOJAS_REQUERIDAS):
        raise ValueError(f"Faltan hojas requeridas. Encontradas: {hojas_existentes}")
    datos = {}
    for hoja in hojas_existentes:
        df = pd.read_excel(xls, sheet_name=hoja)
        datos[hoja] = df
    return datos

def validar_campos(datos: Dict) -> List[str]:
    """Valida que cada hoja contenga los campos mínimos."""
    errores = []
    for rol, df in datos.items():
        campos_req = CAMPOS_POR_ROL[rol]
        cols_lower = [c.lower().strip() for c in df.columns]
        for c in campos_req:
            if c not in cols_lower:
                errores.append(f"Hoja '{rol}' falta campo: {c}")
    return errores
```

### 5.3 Módulo de IA aplicada — `modules/ia_validator.py`

```python
import re
import unicodedata
from fuzzywuzzy import fuzz
import pandas as pd

def normalizar_nombre(nombre: str) -> str:
    """Normaliza nombres: elimina tildes, espacios extra,
    capitaliza correctamente (IA: PLN básico)."""
    if pd.isna(nombre): return ""
    nombre = str(nombre).strip()
    # Quitar tildes
    nombre = unicodedata.normalize('NFD', nombre)
    nombre = ''.join(c for c in nombre if unicodedata.category(c) != 'Mn')
    # Capitalizar tipo título
    nombre = nombre.title()
    # Eliminar espacios múltiples
    nombre = re.sub(r'\s+', ' ', nombre)
    return nombre

def detectar_duplicados(df: pd.DataFrame, umbral: int = 90) -> list:
    """Detecta correos o nombres duplicados por similitud (IA: fuzzy matching).
    Retorna pares de filas con similitud > umbral."""
    duplicados = []
    correos = df['correo'].astype(str).str.lower().tolist()
    for i in range(len(correos)):
        for j in range(i+1, len(correos)):
            score = fuzz.ratio(correos[i], correos[j])
            if score >= umbral:
                duplicados.append((i, j, score))
    return duplicados

def validar_correo_ia(correo: str) -> bool:
    """Validación semántica de formato de correo."""
    patron = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return bool(re.match(patron, str(correo)))

def mapear_encabezados(columnas: list) -> dict:
    """IA: Mapea encabezados equivalentes usando similitud.
    Ej: 'Nombre Completo' → 'nombres', 'Email' → 'correo'"""
    sinonimos = {
        'nombres': ['nombre', 'nombres', 'nombre completo', 'first name'],
        'correo':  ['email', 'correo', 'e-mail', 'mail'],
        'documento':['cedula', 'documento', 'id', 'cc'],
    }
    mapeo = {}
    for col in columnas:
        col_l = col.lower().strip()
        for canon, variantes in sinonimos.items():
            for v in variantes:
                if fuzz.ratio(col_l, v) >= 85:
                    mapeo[col] = canon
                    break
    return mapeo
```

### 5.4 Generador de certificados PDF — `modules/pdf_generator.py`

```python
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.utils import ImageReader
import os

def generar_certificado(datos: dict, plantilla: str, salida: str):
    """Genera un certificado PDF personalizado.
    datos: {nombres, apellidos, rol, ponencia?, evento, fecha}"""
    c = canvas.Canvas(salida, pagesize=landscape(A4))
    w, h = landscape(A4)
    # Fondo / plantilla base
    if os.path.exists(plantilla):
        c.drawImage(plantilla, 0, 0, width=w, height=h)
    # Texto dinámico
    c.setFont("Helvetica-Bold", 32)
    c.setFillColorRGB(0, 0.4, 0.28)  # Verde Unilasallista
    nombre_completo = f"{datos['nombres']} {datos['apellidos']}"
    c.drawCentredString(w/2, h/2 + 40, nombre_completo)
    c.setFont("Helvetica", 16)
    c.setFillColorRGB(0.2, 0.2, 0.2)
    c.drawCentredString(w/2, h/2 - 10, f"Como {datos['rol']} del evento")
    c.drawCentredString(w/2, h/2 - 35, datos.get('evento', ""))
    if 'ponencia' in datos:
        c.drawCentredString(w/2, h/2 - 65, f"Ponencia: {datos['ponencia']}")
    c.setFont("Helvetica-Oblique", 12)
    c.drawCentredString(w/2, 50, f"Bogotá D.C., {datos.get('fecha','')}")
    c.save()
    return salida
```

### 5.5 Servicio de envío SMTP — `modules/mail_service.py`

```python
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import os

def enviar_certificado(destinatario: str, nombre: str,
                       archivo_pdf: str, evento: str) -> dict:
    """Envía el certificado por correo usando SMTP institucional TLS."""
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", 587))
    user = os.getenv("SMTP_USER")
    pwd  = os.getenv("SMTP_PASS")
    from_name = os.getenv("SMTP_FROM_NAME", "Certificados Unilasallista")

    msg = MIMEMultipart()
    msg['From'] = f"{from_name} <{user}>"
    msg['To'] = destinatario
    msg['Subject'] = f"Certificado - {evento} | Universidad de La Salle"

    cuerpo = f"""
    <p>Estimado/a {nombre},</p>
    <p>Adjunto encontrará su certificado como participante del evento
    <strong>{evento}</strong>.</p>
    <p>Cordialmente,<br>Universidad de La Salle</p>
    """
    msg.attach(MIMEText(cuerpo, 'html'))

    # Adjuntar PDF
    with open(archivo_pdf, 'rb') as f:
        part = MIMEBase('application', 'pdf')
        part.set_payload(f.read())
    encoders.encode_base64(part)
    part.add_header('Content-Disposition',
                    f'attachment; filename="{os.path.basename(archivo_pdf)}"')
    msg.attach(part)

    try:
        with smtplib.SMTP(host, port) as server:
            server.starttls()
            server.login(user, pwd)
            server.send_message(msg)
        return {'estado': 'OK', 'correo': destinatario}
    except Exception as e:
        return {'estado': 'ERROR', 'correo': destinatario, 'detalle': str(e)}
```

### 5.6 Trazabilidad con SQLite — `modules/tracker.py`

```python
import sqlite3
from datetime import datetime

def inicializar_db():
    conn = sqlite3.connect('certificados.db')
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS envios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        evento TEXT,
        rol TEXT,
        nombre TEXT,
        correo TEXT,
        estado TEXT,
        detalle TEXT,
        fecha TIMESTAMP
    )""")
    conn.commit(); conn.close()

def registrar_envio(evento, rol, nombre, correo, estado, detalle=""):
    conn = sqlite3.connect('certificados.db')
    c = conn.cursor()
    c.execute("INSERT INTO envios VALUES (NULL,?,?,?,?,?,?,?)",
              (evento, rol, nombre, correo, estado, detalle, datetime.now()))
    conn.commit(); conn.close()

def ya_enviado(evento, correo) -> bool:
    """Evita duplicados accidentales."""
    conn = sqlite3.connect('certificados.db')
    c = conn.cursor()
    c.execute("SELECT 1 FROM envios WHERE evento=? AND correo=? AND estado='OK'",
              (evento, correo))
    existe = c.fetchone() is not None
    conn.close()
    return existe
```

### 5.7 Flujo principal — `app.py`

```python
from flask import Flask, request, render_template, jsonify
from modules.excel_loader import cargar_excel, validar_campos
from modules.ia_validator import normalizar_nombre, detectar_duplicados
from modules.pdf_generator import generar_certificado
from modules.mail_service import enviar_certificado
from modules.tracker import registrar_envio, ya_enviado, inicializar_db
import os

app = Flask(__name__)
inicializar_db()

@app.route('/procesar', methods=['POST'])
def procesar():
    archivo = request.files['excel']
    evento = request.form['evento']
    plantilla = request.form['plantilla']
    ruta_tmp = f"tmp/{archivo.filename}"
    archivo.save(ruta_tmp)

    datos = cargar_excel(ruta_tmp)
    errores = validar_campos(datos)
    if errores:
        return jsonify({'ok': False, 'errores': errores})

    resultados = []
    for rol, df in datos.items():
        # IA: normalizar nombres
        df['nombres_norm'] = df['nombres'].apply(normalizar_nombre)
        df['apellidos_norm'] = df['apellidos'].apply(normalizar_nombre)
        # IA: detectar duplicados
        dups = detectar_duplicados(df)
        if dups:
            print(f"⚠ Posibles duplicados en {rol}: {dups}")

        for _, fila in df.iterrows():
            correo = fila['correo']
            if ya_enviado(evento, correo):
                resultados.append({'correo': correo, 'estado': 'OMITIDO (duplicado)'})
                continue
            pdf = generar_certificado(
                {'nombres': fila['nombres_norm'],
                 'apellidos': fila['apellidos_norm'],
                 'rol': rol, 'evento': evento,
                 'ponencia': fila.get('ponencia', ""),
                 'fecha': "22 de octubre de 2026"},
                plantilla, f"out/{correo}.pdf")
            res = enviar_certificado(correo, fila['nombres_norm'], pdf, evento)
            registrar_envio(evento, rol, fila['nombres_norm'], correo,
                            res['estado'], res.get('detalle', ""))
            resultados.append(res)

    return jsonify({'ok': True, 'total': len(resultados), 'detalle': resultados})

if __name__ == '__main__':
    app.run(debug=True)
```

---

## 6. Aplicación de tópicos de inteligencia artificial

El proyecto integra IA en componentes concretos, diferenciándolos de la programación convencional.

| Tópico | Aplicación | Descripción |
|---|---|---|
| **PLN** | Normalización de nombres | Elimina tildes, capitaliza y unifica formatos (`"juan perez"` → `"Juan Perez"`). |
| **Similitud fuzzy** | Detección de duplicados | `fuzzywuzzy` (Levenshtein) detecta correos o nombres con similitud >90 %. |
| **PLN semántico** | Mapeo de encabezados | Reconoce `"Email"`, `"e-mail"`, `"correo"` → campo canónico `correo`. |
| **Validación inteligente** | Detección de anomalías | Identifica correos inválidos, nombres con caracteres extraños o documentos de longitud atípica (reglas + heurísticas). |
| **IA generativa** | Asistencia en desarrollo | Qwen/ChatGPT para código base, mensajes de correo, documentación y casos de prueba. |
| **Automatización** | Flujo inteligente | Orquestación de validaciones, generación y envío con manejo de errores, reintentos y trazabilidad (principios RPA). |

### 6.1 Programación convencional vs. IA

| Componente | Tipo | Justificación |
|---|---|---|
| Lectura de Excel | Convencional | Librerías estándar (`pandas`). |
| Normalización de nombres | **IA (PLN)** | NFD Unicode y reglas lingüísticas. |
| Generación PDF | Convencional | `reportlab` con coordenadas fijas. |
| Detección de duplicados | **IA (fuzzy)** | Algoritmo de similitud de cadenas. |
| Envío SMTP | Convencional | Protocolo estándar de correo. |
| Mapeo de encabezados | **IA (semántica)** | Reconoce sinónimos por similitud. |
| Redacción de correos | **IA generativa** | Plantillas asistidas por LLM. |

### 6.2 Prompts utilizados en IA generativa

1. **Código:** *"Genera una función en Python con reportlab que cree un certificado en PDF tamaño A4 horizontal, con nombre centrado en verde institucional y texto dinámico para evento y rol."*
2. **PLN:** *"Diseña una función que normalice nombres propios en español, eliminando tildes, capitalizando correctamente y eliminando espacios múltiples."*
3. **Pruebas:** *"Propón 5 casos de prueba para validar el envío de certificados, incluyendo casos borde como correos inválidos, nombres vacíos y archivos duplicados."*

### 6.3 Validación humana del código generado

Todo el código generado por IA fue revisado, ajustado y validado manualmente:

- Se corrigió el manejo de credenciales para usar variables de entorno.
- Se añadieron validaciones adicionales de formato de correo.
- Se integró la trazabilidad con SQLite (no propuesta inicialmente por la IA).
- Se adaptaron los mensajes al contexto institucional lasallista.

---

## 7. Informe de pruebas

### 7.1 Casos de prueba ejecutados

| # | Caso | Entrada | Resultado esperado | Resultado |
|---|---|---|---|---|
| 1 | Carga Excel válido | `archivo.xlsx` con 5 hojas | Lectura exitosa | ✅ OK |
| 2 | Excel sin hojas | Archivo incompleto | Error descriptivo | ✅ OK |
| 3 | Nombre con tildes | `"María José Pérez"` | `"Maria Jose Perez"` | ✅ OK |
| 4 | Correo inválido | `"juan@sinDominio"` | Rechazado | ✅ OK |
| 5 | Duplicado detectado | 2 correos 95 % similares | Alerta de duplicado | ✅ OK |
| 6 | Encabezado "Email" | Columna `Email` | Mapea a `correo` | ✅ OK |
| 7 | Generación PDF | Datos válidos | PDF generado | ✅ OK |
| 8 | Envío SMTP exitoso | Destinatario válido | Correo enviado | ✅ OK |
| 9 | Envío fallido | Destinatario inexistente | Registro ERROR | ✅ OK |
| 10 | Reenvío duplicado | Mismo evento + correo | Omitido | ✅ OK |

### 7.2 Evidencia de ejecución (consola)

```
[INFO] Cargando archivo: evento_congreso.xlsx
[INFO] Hojas detectadas: 5/5 ✓
[IA] Normalizando 47 nombres...
[IA] Detectados 2 posibles duplicados en Ponentes
[PDF] Generando certificado: maria.perez@correo.com
[SMTP] Enviando a maria.perez@correo.com ... OK
[DB] Registro #123 insertado
[INFO] Total procesados: 47 | OK: 45 | ERROR: 1 | OMITIDO: 1
```

### 7.3 Errores identificados y mejoras

| Error | Mejora |
|---|---|
| Algunos PDFs excedían 5 MB con imágenes de alta resolución. | Compresión automática de imágenes antes de incrustar. |
| Timeout en envíos masivos. | Cola asíncrona con Celery. |
| Problemas con caracteres especiales (ñ, apellidos compuestos). | Diccionario de excepciones para `De`, `Del`, `Mc`, etc. |

---

## 8. Seguridad y protección de datos

- 🔐 **Credenciales:** en variables de entorno (`.env`) o gestor de secretos; nunca en el código ni en el repositorio.
- 🔒 **Transporte:** todos los envíos SMTP usan TLS (puerto 587).
- 📄 **PDFs protegidos:** opcionalmente cifrados con contraseña (número de documento del participante).
- 🛡️ **Datos personales:** cumplimiento de la Ley 1581 de 2012 (Habeas Data); los datos solo se usan para el fin del certificado.
- 📋 **Auditoría:** toda operación queda registrada en SQLite con fecha, usuario y resultado.
- 🧹 **Limpieza:** archivos temporales y PDFs se eliminan tras el envío.

> ⚠️ **Nota ética:** el prototipo usa únicamente datos ficticios o autorizados. En producción se requiere consentimiento informado de los participantes y validación por parte de la oficina de protección de datos de la Universidad.

---

## 9. Sustentación y reflexión final

### 9.1 Viabilidad institucional

- Usa el SMTP institucional ya contratado (costo cero).
- Está construida en Python, soportado por la oficina de TI.
- Es modular: cada dependencia puede configurarla de forma independiente.
- Respeta la normativa colombiana de protección de datos.
- Permite escalar a servicios cloud (SendGrid, AWS SES).

### 9.2 Limitaciones del prototipo

- No incluye interfaz gráfica completa (se demuestra vía API).
- El envío masivo es secuencial (requiere Celery para producción).
- La detección de duplicados usa un umbral fijo (podría entrenarse un modelo).
- No integra firma digital de certificados (requiere certificación FAURE o similar).

### 9.3 Reflexión sobre el uso de IA

La IA aportó valor en tres dimensiones:

1. **Calidad de datos:** la normalización con PLN mejoró la presentación final de los certificados.
2. **Prevención de errores:** la detección fuzzy evitó envíos repetidos.
3. **Productividad:** la IA generativa redujo ~40 % el tiempo de codificación, permitiendo enfocarse en diseño y validación.

> **Conclusión clave:** la IA no reemplaza al desarrollador, lo aumenta. La validación humana, el contexto institucional y las decisiones éticas siguen siendo responsabilidad del estudiante y de la universidad.

### 9.4 Criterios de evaluación (autoevaluación)

| Criterio | Peso |
|---|---|
| Investigación y justificación de arquitectura y correo | 20 % |
| Diseño y funcionalidad del prototipo | 30 % |
| Aplicación y argumentación de tópicos de IA | 20 % |
| Pruebas, seguridad y manejo de errores | 15 % |
| Documentación, sustentación y reflexión sobre IA | 15 % |
| **Total** | **100 %** |

---

## ▶️ Cómo ejecutarlo (guía rápida)

```bash
# 1. Clonar e instalar dependencias
pip install flask pandas openpyxl reportlab fuzzywuzzy python-dotenv

# 2. Configurar credenciales SMTP en .env (ver sección 4.3)

# 3. Ejecutar
python app.py

# 4. Procesar un evento
curl -X POST http://localhost:5000/procesar \
  -F "excel=@data/ejemplo_evento.xlsx" \
  -F "evento=Congreso 2026" \
  -F "plantilla=templates/certificado_base.pdf"
```

> Esta guía es una adición mía a partir del código del documento original (endpoint `/procesar` y variables `.env`). No aparecía textualmente en el HTML.

---

*Proyecto Certificado Unilasallista · Tópicos de Inteligencia Artificial · Universidad de La Salle · 2026-II*

> *"Deleznables son las obras que se siguen de la experiencia y carecen de fundamento teórico."* — Leonardo da Vinci
