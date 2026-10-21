"""Módulos del sistema **Certificado Unilasallista**.

Cada módulo encapsula una capacidad del flujo:

============  ==========================================================
Módulo        Responsabilidad
============  ==========================================================
excel_loader  Carga y validación estructural del archivo Excel (RF1, RF2)
ia_validator  IA aplicada: PLN, similitud fuzzy, anomalías (sección 6)
pdf_generator Generación de certificados PDF (RF3)
mail_service  Envío por SMTP institucional con TLS (RF4, RF5)
tracker       Trazabilidad y auditoría en SQLite (RF6)
============  ==========================================================
"""

__all__ = [
    "excel_loader",
    "ia_validator",
    "pdf_generator",
    "mail_service",
    "tracker",
]
