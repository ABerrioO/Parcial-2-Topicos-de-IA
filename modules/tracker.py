"""Trazabilidad y auditoría de envíos en SQLite (RF6).

Se registran los envíos **exitosos, fallidos, omitidos y pendientes**, con
fecha, rol, dependencia y detalle del error. La base permite:

  * Auditar qué se envió a quién y en qué momento (README §8).
  * Evitar certificados duplicados en reprocesos del mismo evento.
  * Reportar estadísticas por evento, rol y estado (multi-dependencia, RF7).
"""

from __future__ import annotations

import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from config import APP_CONFIG

log = logging.getLogger(__name__)

#: Estados válidos de un envío.
ESTADOS = ("PENDIENTE", "OK", "ERROR", "OMITIDO", "GENERADO")


def ruta_db() -> Path:
    """Ruta del archivo SQLite configurado."""
    return APP_CONFIG.db_path


@contextmanager
def conexion() -> Iterator[sqlite3.Connection]:
    """Abre una conexión con control de commit/rollback."""
    conn = sqlite3.connect(str(ruta_db()))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def inicializar_db() -> Path:
    """Crea las tablas si no existen y devuelve la ruta de la base."""
    ruta_db().parent.mkdir(parents=True, exist_ok=True)
    with conexion() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS eventos (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre      TEXT NOT NULL UNIQUE,
                dependencia TEXT,
                descripcion TEXT,
                creado_en   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS envios (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                evento      TEXT NOT NULL,
                rol         TEXT,
                nombre      TEXT,
                correo      TEXT,
                estado      TEXT NOT NULL,
                detalle     TEXT DEFAULT '',
                dependencia TEXT,
                fecha       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_envios_evento ON envios(evento);
            CREATE INDEX IF NOT EXISTS idx_envios_correo ON envios(correo);
            CREATE INDEX IF NOT EXISTS idx_envios_estado ON envios(estado);
            """
        )
    log.info("[DB] Base de datos lista: %s", ruta_db().name)
    return ruta_db()


# ── Eventos ───────────────────────────────────────────────────────────────
def registrar_evento(
    evento: str, dependencia: str | None = None, descripcion: str = ""
) -> int:
    """Registra (o recupera) un evento. Devuelve su identificador."""
    with conexion() as conn:
        cursor = conn.execute(
            """
            INSERT INTO eventos (nombre, dependencia, descripcion)
            VALUES (?, ?, ?)
            ON CONFLICT(nombre) DO UPDATE SET
                dependencia = COALESCE(excluded.dependencia, eventos.dependencia),
                descripcion = COALESCE(NULLIF(excluded.descripcion, ''), eventos.descripcion)
            """,
            (evento, dependencia, descripcion),
        )
        if cursor.lastrowid:
            return int(cursor.lastrowid)
        fila = conn.execute(
            "SELECT id FROM eventos WHERE nombre = ?", (evento,)
        ).fetchone()
        return int(fila["id"]) if fila else 0


def listar_eventos(limite: int = 100) -> List[Dict[str, Any]]:
    """Eventos registrados con el conteo de envíos associated."""
    with conexion() as conn:
        filas = conn.execute(
            """
            SELECT e.nombre, e.dependencia, e.creado_en,
                   COUNT(s.id) AS total_envios,
                   SUM(CASE WHEN s.estado = 'OK' THEN 1 ELSE 0 END) AS ok,
                   SUM(CASE WHEN s.estado = 'ERROR' THEN 1 ELSE 0 END) AS errores
            FROM eventos e
            LEFT JOIN envios s ON s.evento = e.nombre
            GROUP BY e.id
            ORDER BY e.creado_en DESC
            LIMIT ?
            """,
            (limite,),
        ).fetchall()
    return [dict(f) for f in filas]


# ── Envíos ────────────────────────────────────────────────────────────────
def registrar_envio(
    evento: str,
    rol: str,
    nombre: str,
    correo: str,
    estado: str,
    detalle: str = "",
    dependencia: str | None = None,
) -> int:
    """Registra un envío en la base de datos y devuelve su identificador."""
    estado = (estado or "PENDIENTE").upper()
    with conexion() as conn:
        cursor = conn.execute(
            """
            INSERT INTO envios (evento, rol, nombre, correo, estado, detalle, dependencia, fecha)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                evento,
                rol,
                nombre,
                correo,
                estado,
                detalle or "",
                dependencia,
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        nuevo_id = int(cursor.lastrowid)
    log.info("[DB] Registro #%d insertado (%s · %s)", nuevo_id, estado, correo)
    return nuevo_id


def ya_enviado(evento: str, correo: str) -> bool:
    """True si el correo ya recibió un certificado enviado con éxito.

    Evita duplicados accidentales al reprocesar un evento (RF6).
    """
    correo = (correo or "").strip().lower()
    if not correo:
        return False
    with conexion() as conn:
        fila = conn.execute(
            """
            SELECT 1 FROM envios
            WHERE evento = ? AND LOWER(correo) = ? AND estado = 'OK'
            LIMIT 1
            """,
            (evento, correo),
        ).fetchone()
    return fila is not None


def ya_registrado(evento: str, correo: str) -> bool:
    """True si el correo aparece en la base para ese evento (cualquier estado)."""
    correo = (correo or "").strip().lower()
    with conexion() as conn:
        fila = conn.execute(
            "SELECT 1 FROM envios WHERE evento = ? AND LOWER(correo) = ? LIMIT 1",
            (evento, correo),
        ).fetchone()
    return fila is not None


def listar_envios(
    evento: str | None = None,
    estado: str | None = None,
    limite: int = 200,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """Consulta filtrada de envíos (trazabilidad)."""
    condiciones: List[str] = []
    parametros: List[Any] = []

    if evento:
        condiciones.append("evento = ?")
        parametros.append(evento)
    if estado:
        condiciones.append("estado = ?")
        parametros.append(estado.upper())

    where = f"WHERE {' AND '.join(condiciones)}" if condiciones else ""
    parametros.extend([limite, offset])

    with conexion() as conn:
        filas = conn.execute(
            f"""
            SELECT id, evento, rol, nombre, correo, estado, detalle, dependencia, fecha
            FROM envios
            {where}
            ORDER BY id DESC
            LIMIT ? OFFSET ?
            """,
            parametros,
        ).fetchall()
    return [dict(f) for f in filas]


def estadisticas(evento: str | None = None) -> Dict[str, Any]:
    """Resumen de envíos: totales por estado, rol y dependencia."""
    where = "WHERE evento = ?" if evento else ""
    parametros = (evento,) if evento else ()

    with conexion() as conn:
        por_estado = {
            fila["estado"]: fila["total"]
            for fila in conn.execute(
                f"SELECT estado, COUNT(*) AS total FROM envios {where} GROUP BY estado",
                parametros,
            ).fetchall()
        }
        por_rol = {
            (fila["rol"] or "—"): fila["total"]
            for fila in conn.execute(
                f"SELECT rol, COUNT(*) AS total FROM envios {where} GROUP BY rol ORDER BY total DESC",
                parametros,
            ).fetchall()
        }
        por_dependencia = {
            (fila["dependencia"] or "—"): fila["total"]
            for fila in conn.execute(
                f"SELECT dependencia, COUNT(*) AS total FROM envios {where} GROUP BY dependencia",
                parametros,
            ).fetchall()
        }
        total = sum(por_estado.values())

    return {
        "evento": evento,
        "total": total,
        "por_estado": {estado: por_estado.get(estado, 0) for estado in ESTADOS},
        "por_rol": por_rol,
        "por_dependencia": por_dependencia,
        "tasa_exito": round(por_estado.get("OK", 0) / total * 100, 1) if total else 0.0,
    }


def limpiar_registros(evento: Optional[str] = None) -> int:
    """Borra los envíos de un evento (o todos). Devuelve las filas borradas."""
    with conexion() as conn:
        if evento:
            cursor = conn.execute("DELETE FROM envios WHERE evento = ?", (evento,))
        else:
            cursor = conn.execute("DELETE FROM envios")
        return cursor.rowcount
