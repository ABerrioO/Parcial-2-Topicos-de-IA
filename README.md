# 🎓 Certificado Unilasallista

**Proyecto aplicado — Tópicos de Inteligencia Artificial**
Universidad de La Salle · 2026-II · Parcial

Aplicación web modular que automatiza la **generación y el envío de certificados académicos** para eventos institucionales. Cualquier dependencia universitaria puede cargar participantes desde Excel, validarlos con técnicas de IA aplicada, generar el certificado en PDF y enviarlo por correo institucional, dejando **trazabilidad completa** de cada envío.

---

## Índice

1. [Resumen](#1-resumen)
2. [Flujo del proceso](#2-flujo-del-proceso)
3. [Tecnologías utilizadas](#3-tecnologías-utilizadas)
4. [Requisitos previos](#4-requisitos-previos)
5. [Instalación](#5-instalación)
6. [Configuración](#6-configuración)
7. [Cómo ejecutarlo](#7-cómo-ejecutarlo)
8. [Uso de la aplicación](#8-uso-de-la-aplicación)
9. [Formato del archivo Excel](#9-formato-del-archivo-excel)
10. [Endpoints de la API](#10-endpoints-de-la-api)
11. [Aplicación de tópicos de IA](#11-aplicación-de-tópicos-de-ia)
12. [Estructura del proyecto](#12-estructura-del-proyecto)
13. [Pruebas](#13-pruebas)
14. [Recursos estáticos y plantilla](#14-recursos-estáticos-y-plantilla)
15. [Seguridad y protección de datos](#15-seguridad-y-protección-de-datos)
16. [Solución de problemas](#16-solución-de-problemas)

---

## 1. Resumen

| Capacidad | Descripción |
|---|---|
| 📊 **Carga inteligente** | Lee un Excel con 5 hojas: `Asistentes`, `Ponentes`, `Conferenciantes`, `Evaluadores` y `Organizadores`. |
| 🤖 **Validación con IA** | Normaliza nombres (PLN), detecta duplicados (similitud fuzzy) y mapea encabezados equivalentes. |
| 📜 **Generación de PDF** | Certificados personalizados en A4 horizontal desde plantilla institucional con datos dinámicos. |
| 📧 **Envío SMTP** | Servidor institucional con TLS/SSL, autenticación, reintentos y modo simulación. |
| 🔒 **Seguridad** | Credenciales en variables de entorno, cifrado TLS y PDF opcionalmente protegido. |
| 📈 **Trazabilidad** | Registro en SQLite de envíos `OK`, `ERROR`, `OMITIDO` y `PENDIENTE`. |

---

## 2. Flujo del proceso

```
Carga Excel → Validación IA → Plantilla → Generar PDF → Envío SMTP → Registro
```

1. **Carga Excel** — se leen las 5 hojas y se normalizan los encabezados por similitud semántica.
2. **Validación IA** — se normalizan nombres, se detectan duplicados (correos y nombres) y anomalías.
3. **Plantilla** — se selecciona el PDF institucional (`templates/*.pdf`); por defecto `templates/certificado_base.pdf`.
4. **Generar PDF** — `reportlab` + `pypdf` superponen los datos del participante (nombre, rol, evento, ponencia y firmas) sobre la plantilla institucional, conservando su diseño original.
5. **Envío SMTP** — el certificado se adjunta y se envía por correo institucional (o se simula).
6. **Registro** — cada envío queda auditado en SQLite para trazabilidad y control de duplicados.

---

## 3. Tecnologías utilizadas

| Tecnología | Rol |
|---|---|
| **Python 3.11+** | Lenguaje principal |
| **Flask** | Framework web (API REST + interfaz HTML) |
| **pandas + openpyxl** | Lectura y procesamiento del Excel |
| **reportlab** | Capa de datos y textos sobre el certificado PDF |
| **pypdf** | Lectura de la plantilla, fusión de capas y cifrado del PDF |
| **fuzzywuzzy + python-Levenshtein** | Similitud fuzzy para duplicados y mapeo de encabezados |
| **python-dotenv** | Carga de credenciales desde `.env` |
| **Pillow** | Compresión del logotipo y de las plantillas |
| **SQLite** | Base de datos de trazabilidad (`certificados.db`) |
| **pytest** | Pruebas automatizadas |

---

## 4. Requisitos previos

- **Python 3.11 o superior** (probado en 3.11–3.14).
- Acceso a un servidor **SMTP institucional** (opcional: el modo simulación permite trabajar sin credenciales).
- Un libro Excel con las 5 hojas requeridas (hay uno de ejemplo en `data/ejemplo_evento.xlsx`).

---

## 5. Instalación

### 5.1 Entorno virtual (recomendado)

**Windows (PowerShell):**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**Linux / macOS:**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 5.2 Instalación mínima (sin entorno virtual)

```bash
pip install -r requirements.txt
```

> **Nota:** en PowerShell puede ser necesario `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` para activar el entorno virtual.

---

## 6. Configuración

### 6.1 Crear el archivo `.env`

El proyecto lee su configuración de `.env` (ya está en `.gitignore`). Hay una plantilla lista en `.env.example`:

```bash
# Windows
copy .env.example .env

# Linux / macOS
cp .env.example .env
```

### 6.2 Variables de entorno

**Correo SMTP:**

| Variable | Por defecto | Descripción |
|---|---|---|
| `SMTP_HOST` | `smtp.office365.com` | Servidor SMTP institucional |
| `SMTP_PORT` | `587` | Puerto (587 = STARTTLS, 465 = SSL implícito) |
| `SMTP_USER` | — | Usuario de autenticación |
| `SMTP_PASS` | — | Contraseña de autenticación |
| `SMTP_USE_TLS` | `True` | Activa STARTTLS |
| `SMTP_USE_SSL` | `False` | Activa SSL implícito |
| `SMTP_FROM_NAME` | `Certificados Unilasallista` | Nombre del remitente |
| `SMTP_TIMEOUT` | `30` | Timeout de conexión en segundos |
| `SMTP_MAX_REINTENTOS` | `3` | Intentos ante fallos transitorios |
| `SMTP_MODO_SIMULACION` | `True` | `False` habilita el envío real de correos |

**Aplicación y datos:**

| Variable | Por defecto | Descripción |
|---|---|---|
| `SECRET_KEY` | clave de desarrollo | Secreto de Flask (generar con `python -c "import secrets;print(secrets.token_hex(32))"`) |
| `DB_PATH` | `certificados.db` | Ruta de la base SQLite de trazabilidad |
| `MAX_UPLOAD_MB` | `20` | Tamaño máximo del archivo Excel |
| `PDF_PROTEGER` | `False` | Cifra el PDF con el documento del participante |
| `PLANTILLA_BASE` | `certificado_base.pdf` | Plantilla institucional usada por defecto (dentro de `templates/`) |
| `FECHA_CERTIFICADO` | `22 de octubre de 2026` | Fecha impressa en el certificado |
| `HOST` | `127.0.0.1` | Host del servidor Flask |
| `PORT` | `5000` | Puerto del servidor Flask |
| `FLASK_DEBUG` | `0` | `1` activa el modo depuración |

**IA y umbrales:**

| Variable | Por defecto | Descripción |
|---|---|---|
| `UMBRAL_DUPLICADOS` | `90` | Similitud mínima (%) para marcar duplicados |
| `UMBRAL_ENCABEZADOS` | `85` | Similitud mínima (%) para mapear un encabezado |
| `UMBRAL_NOMBRES` | `92` | Umbral de similitud para nombres duplicados |
| `PLN_PRESERVAR_ENIE` | `False` | Conserva la `ñ` en la normalización |
| `DOCUMENTO_LONGITUD_MIN` | `5` | Mínimo de dígitos válidos en el documento |
| `DOCUMENTO_LONGITUD_MAX` | `20` | Máximo de dígitos válidos en el documento |
| `LLM_API_KEY` | vacío | Habilita la redacción de correos con IA generativa |
| `LLM_BASE_URL` | `https://api.openai.com/v1` | Endpoint compatible con OpenAI |
| `LLM_MODEL` | `gpt-4o-mini` | Modelo usado para redactar los mensajes |

### 6.3 Modo simulación vs. envío real

Por defecto el sistema **no envía correos reales**: registra la intención de envío en la base de datos y la trazabilidad, lo que permite demostrar y probar todo el flujo de forma segura.

Para activar el envío real:

```ini
SMTP_MODO_SIMULACION=False
SMTP_USER=certificados@lasalle.edu.co
SMTP_PASS=<clave-real>
```

---

## 7. Cómo ejecutarlo

### 7.1 Modo local (desarrollo)

```bash
python app.py
```

Salida esperada:

```
[INFO] Certificado Unilasallista escuchando en http://127.0.0.1:5000
 * Running on http://127.0.0.1:5000
```

Luego abra **<http://127.0.0.1:5000>** en el navegador.

### 7.2 Con depuración (recarga automática)

```bash
# Windows
$env:FLASK_DEBUG="1"; python app.py

# Linux / macOS
FLASK_DEBUG=1 python app.py
```

### 7.3 Con puerto y host personalizados

```bash
# Windows
$env:HOST="0.0.0.0"; $env:PORT="8080"; python app.py

# Linux / macOS
HOST=0.0.0.0 PORT=8080 python app.py
```

### 7.4 Procesar un evento por línea de comandos

```bash
curl -X POST http://localhost:5000/procesar \
  -F "excel=@data/ejemplo_evento.xlsx" \
  -F "evento=Congreso 2026" \
  -F "dependencia=Facultad de Ingeniería" \
  -F "plantilla=templates/certificado_base.pdf"
```

Para **generar los certificados PDF sin enviarlos** por correo:

```bash
curl -X POST http://localhost:5000/procesar \
  -F "excel=@data/ejemplo_evento.xlsx" \
  -F "evento=Congreso 2026" \
  -F "dependencia=Facultad de Ingeniería" \
  -F "modo=generar"
```

Para **solo validar** (sin generar PDF ni enviar correos), use el modo `validar`:

```bash
curl -X POST http://localhost:5000/api/validar \
  -F "excel=@data/ejemplo_evento.xlsx"
```

---

## 8. Uso de la aplicación

1. **Abrir la interfaz** en `http://127.0.0.1:5000`.
2. **Cargar el Excel** con los participantes (`.xlsx` o `.xlsm`).
3. **Escribir el nombre del evento** y la **dependencia** firmante.
4. **Elegir la plantilla** (por defecto `templates/certificado_base.pdf`).
5. **Validar con IA** (`/api/validar`): muestra duplicados, anomalías y normalización sin emitir certificados.
6. **Generar certificados (sin enviar)** (`/procesar` con `modo=generar`): produce los archivos PDF en `out/` y los registra como `GENERADO` sin emitir correos.
7. **Procesar y enviar correos** (`/procesar`): genera los PDF, los envía por correo (o simulación SMTP) y registra los envíos `OK`.
8. **Ver o descargar certificados**: use el botón **👁 Ver** en cualquier fila del resultado o trazabilidad para visualizar el certificado directamente en el visor de la página, o el botón **⬇** para descargarlo.
9. **Revisar la trazabilidad**: envíos, estadísticas por estado/rol/dependencia y listado de eventos.

La interfaz muestra en vivo el estado de SMTP (host, puerto, usuario y si está en modo simulación), y el botón de diagnóstico permite verificar la conexión con el servidor de correo.

---

## 9. Formato del archivo Excel

El libro debe contener las **cinco hojas** con estos nombres exactos: `Asistentes`, `Ponentes`, `Conferenciantes`, `Evaluadores`, `Organizadores`.

### Campos mínimos por hoja

| Hoja | Campos obligatorios | Campos opcionales |
|---|---|---|
| `Asistentes` | `nombres`, `apellidos`, `correo` | `tipo_participacion` |
| `Ponentes` | `nombres`, `apellidos`, `correo`, `documento`, `ponencia` | `ponencia` |
| `Conferenciantes` | `nombres`, `apellidos`, `correo`, `documento`, `conferencia` | `conferencia` |
| `Evaluadores` | `nombres`, `apellidos`, `correo`, `documento` | `area`, `comite` |
| `Organizadores` | `nombres`, `apellidos`, `correo` | `cargo` |

### Encabezados alternativos (mapeo semántico)

No es necesario usar los nombres exactos: el módulo de IA reconoce sinónimos por similitud y los renombra automáticamente.

| Canónico | Sinónimos aceptados |
|---|---|
| `nombres` | Nombre, Nombre Completo, Nombres y Apellidos, First Name |
| `apellidos` | Apellido, Apellidos, Last Name |
| `correo` | Email, e-mail, Mail, Correo, Correo Institucional |
| `documento` | Cédula, CC, ID, Número de Documento |
| `ponencia` | Ponencia, Título de la Ponencia |
| `conferencia` | Conferencia, Charla |
| `area` | Área, Área de Evaluación |
| `comite` | Comité, Comité Evaluador |
| `cargo` | Cargo, Rol Institucional |

> Ejemplo: una hoja con las columnas `Nombre Completo`, `Apellidos`, `Email` y `Cédula` se normaliza a `nombres`, `apellidos`, `correo` y `documento`.

Existe un libro de ejemplo listo para usar en **`data/ejemplo_evento.xlsx`**, que incluye casos borde (nombres con tildes y mayúsculas, correos inválidos y encabezados alternativos).

---

## 10. Endpoints de la API

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/` | Interfaz web principal |
| `POST` | `/procesar` | Procesa un evento completo (valida, genera PDF, envía y registra) |
| `POST` | `/api/validar` | Valida el Excel y devuelve el informe de IA, sin enviar |
| `GET` | `/api/salud` | Estado del servicio y de sus dependencias |
| `GET` | `/api/config` | Configuración efectiva (sin exponer secretos) |
| `GET` | `/api/plantillas` | Plantillas PDF disponibles en el servidor |
| `POST` | `/api/smtp/verificar` | Prueba de conexión con el servidor SMTP |
| `GET` | `/api/envios` | Trazabilidad de envíos (`?evento=`, `?estado=`, `?limite=`, `?offset=`) |
| `GET` | `/api/estadisticas` | Resumen estadístico (`?evento=`) |
| `GET` | `/api/eventos` | Eventos registrados |
| `GET` | `/certificados/<correo>` | Visualización en el navegador o descarga (`?descargar=1`) del PDF generado |
| `GET` | `/api/certificados` | Listado de certificados PDF disponibles en el servidor |

Ejemplo de respuesta de `/api/salud`:

```json
{
  "ok": true,
  "servicio": "Certificado Unilasallista",
  "version": "1.0.0",
  "ia": { "pln": true, "fuzzy": true, "llm": false },
  "smtp": {
    "host": "smtp.office365.com",
    "puerto": 587,
    "modo_simulacion": true,
    "configurado": false,
    "transporte_seguro": true
  },
  "base_datos": "certificados.db"
}
```

---

## 11. Aplicación de tópicos de IA

| Tópico de IA | Componente | Aplicación |
|---|---|---|
| **PLN** | `modules/ia_validator.py` | Normalización de nombres propios: descomposición Unicode (NFD), eliminación de diacríticos, capitalización con partículas en minúscula (`de`, `del`, `Mc`) y colapso de espacios. `"  maría  jose pérez "` → `"Maria Jose Perez"`. |
| **Similitud fuzzy** | `modules/ia_validator.py` | Detección de duplicados por `fuzzywuzzy`/Levenshtein, tanto por correo como por nombre completo, con umbral configurable. |
| **PLN semántico** | `modules/ia_validator.py` | Mapeo de encabezados equivalentes a campos canónicos mediante similitud contra un diccionario de sinónimos. |
| **Validación inteligente** | `modules/ia_validator.py` | Heurísticas para correos inválidos, nombres vacíos, caracteres no permitidos y documentos de longitud atípica. |
| **IA generativa** | `modules/ia_validator.py` | Redacción asistida del correo con un LLM compatible con OpenAI; **con respaldo automático** en plantillas institucionales ante cualquier fallo, de modo que el envío nunca se detiene. |
| **Automatización** | `app.py` | Orquestación del flujo completo con manejo de errores, reintentos y trazabilidad. |

> La parte generativa es **opcional**: sin `LLM_API_KEY` el sistema funciona por completo con plantillas deterministas, sin conexión y sin costo.

---

## 12. Estructura del proyecto

```
Parcial2TopicosIA/
├── app.py                        # Punto de entrada Flask (rutas web + API)
├── config.py                     # Rutas, SMTP, umbrales de IA y logging
├── requirements.txt              # Dependencias
├── .env                          # Credenciales locales (no versionado)
├── .env.example                  # Plantilla de configuración
├── especificaciones.md            # Documento de la propuesta técnica
├── certificados.db               # Base SQLite de trazabilidad
│
├── modules/
│   ├── __init__.py
│   ├── excel_loader.py           # Carga y validación del Excel (RF1, RF2)
│   ├── ia_validator.py           # Módulo de IA (PLN, duplicados, LLM)
│   ├── pdf_generator.py          # Generación de certificados (RF3)
│   ├── mail_service.py           # Envío SMTP con TLS y reintentos (RF4, RF5)
│   └── tracker.py                # Trazabilidad en SQLite (RF6, RF7)
│
├── templates/
│   ├── index.html                # Interfaz web
│   └── certificado_base.pdf      # Plantilla institucional de fondo
│
├── static/
│   └── logo_unilasalle.png       # Logotipo institucional
│
├── data/
│   └── ejemplo_evento.xlsx       # Libro de ejemplo con las 5 hojas
│
├── tools/
│   └── generar_recursos.py       # Regenera logo, plantilla y Excel de ejemplo
│
├── tests/
│   ├── conftest.py               # Fixtures (libros Excel, BD y SMTP aislados)
│   ├── test_flujo.py             # Pruebas del flujo completo y de la API
│   └── test_ia_validator.py      # Pruebas del módulo de IA
│
├── out/                          # Certificados PDF generados (temporal)
└── tmp/                          # Archivos temporales de carga
```

---

## 13. Pruebas

```bash
# Suite completa
python -m pytest -v

# Solo un archivo
python -m pytest tests/test_flujo.py -v

# Con cobertura de la salida
python -m pytest --tb=short
```

Resultado actual: **50 pruebas, todas en verde**.

Las pruebas usan fixtures que aíslan la base de datos, las carpetas de salida y el SMTP, por lo que **no envían correos reales ni modifican** `certificados.db`.

---

## 14. Recursos estáticos y plantilla

Para regenerar el logotipo, la plantilla base y el Excel de ejemplo:

```bash
python tools/generar_recursos.py
```

Salida esperada:

```
[OK] Logotipo:      static/logo_unilasalle.png
[OK] Plantilla:     templates/certificado_base.pdf
[OK] Excel ejemplo: data/ejemplo_evento.xlsx
```

> `templates/certificado_base.pdf` es un **recurso editable**: si ya existe, el script **no lo sobrescribe** (informa que se conserva). Para rehacerlo desde cero, elimínalo o mueve el archivo a otra carpeta antes de ejecutar el script.

Las plantillas adicionales se detectan automáticamente: basta con dejar un `.pdf` en `templates/` y aparecerá en el selector de la interfaz y en `GET /api/plantillas`.

### 14.1 Cómo se compone el certificado

El PDF institucional se usa como **capa de fondo real** (no como imagen ni como diseño reconstruido en código):

1. `modules/pdf_generator.py` lee la plantilla con `pypdf` y extrae sus textos con posición, tamaño y fuente.
2. Se localizan los marcadores (`<PROMEDIO>`, `<NOMBRE>`, `<CURSO>`) y las líneas de texto que deben reemplazarse por los datos del participante.
3. Se genera una **capa superpuesta** (`reportlab`) del mismo tamaño de página: rectángulos blancos que tapan las líneas sustituidas + los valores dinámicos de cada participante.
4. `pypdf` fusiona ambas capas (`merge_page`) conservando el diseño, los logos y el formato original (A4 horizontal o el tamaño propio de la plantilla).

| Marcador / línea | Valor que se dibuja |
| --- | --- |
| `OTORGA el <PROMEDIO> A:` | `OTORGA el CERTIFICADO DE PARTICIPACIÓN A:` (o `RECONOCIMIENTO`) |
| `<NOMBRE>` | Nombre y apellidos del participante |
| `Por la MODALIDAD <CURSO>` | Modalidad (ponente, conferenciante, asistente, curso…) |
| Fecha del evento | Fecha y municipio de entrega |
| Dependencia | `LA FACULTAD DE INGENIERÍAS` |
| Código | Código de registro (esquina inferior izquierda) |

Si la plantilla no existe, está dañada o no contiene los marcadores esperados, el sistema **cae automáticamente al diseño propio** (A4 horizontal) para no detener la generación.

---

## 15. Seguridad y protección de datos

- 🔐 **Credenciales** — solo en `.env` o variables de entorno; nunca en el código ni en el repositorio (`.env` está en `.gitignore`).
- 🔒 **Transporte** — los envíos usan TLS (puerto 587) o SSL implícito (puerto 465).
- 📄 **PDFs protegidos** — opcionalmente cifrados con el número de documento del participante (`PDF_PROTEGER=True`).
- 🛡️ **Datos personales** — los datos se usan únicamente para emitir el certificado (Ley 1581 de 2012, Habeas Data).
- 📋 **Auditoría** — toda operación queda registrada en SQLite con fecha, rol, dependencia, estado y detalle del error.
- 🧹 **Limpieza** — los archivos temporales y los PDF se eliminan tras el envío.
- 🚫 **Idempotencia** — un correo que ya fue enviado con éxito en el mismo evento se marca `OMITIDO`, evitando duplicados.

> ⚠️ Use únicamente datos ficticios o autorizados. Para producción se requiere consentimiento informado de los participantes y validación de la oficina de protección de datos de la Universidad.

---

## 16. Solución de problemas

| Síntoma | Causa probable | Solución |
|---|---|---|
| `ModuleNotFoundError: No module named 'flask'` | Dependencias no instaladas | `pip install -r requirements.txt` |
| `Faltan hojas requeridas: ...` | El Excel no tiene las 5 hojas | Use `data/ejemplo_evento.xlsx` como base o cree las hojas faltantes con los nombres exactos |
| `Hoja 'X' falta campo: correo` | Encabezado no reconocido | Renombre la columna a `correo` (o a un sinónimo como `Email`) y reintente |
| `SMTP no configurado` | Faltan `SMTP_USER` o `SMTP_PASS` | Complete el `.env`, o mantenga `SMTP_MODO_SIMULACION=True` |
| `El archivo supera el límite de N MB` | Excel muy pesado | Aumente `MAX_UPLOAD_MB` o divida el evento en archivos más pequeños |
| `Error de autenticación SMTP` | Credenciales incorrectas o MFA activo | Verifique la clave y el uso de contraseña de aplicación en Office 365 |
| Los correos no llegan | Sigue activo el modo simulación | Ponga `SMTP_MODO_SIMULACION=False` |
| `Address already in use` | El puerto 5000 está ocupado | `PORT=8080 python app.py` |

---

<div align="center">

**Proyecto Certificado Unilasallista** · Tópicos de Inteligencia Artificial · Universidad de La Salle · 2026-II

</div>
