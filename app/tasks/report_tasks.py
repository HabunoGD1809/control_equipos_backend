import logging
import csv
import uuid
from pathlib import Path
from typing import Dict, Any
from datetime import datetime

from app.worker import celery_app
from app.db.session import SessionLocal
from app.core.storage import UPLOAD_DIR
from app.models.notificacion import Notificacion
from app.services.reporte import reporte_service
from fpdf import FPDF

logger = logging.getLogger(__name__)

@celery_app.task(name="tasks.cleanup_report")
def task_cleanup_report(filepath: str):
    path = Path(filepath)
    if path.exists():
        path.unlink()
        logger.info(f"🗑️ Reporte expirado eliminado: {filepath}")
    return True

@celery_app.task(name="tasks.generate_report")
def task_generate_report(report_type: str, filters: Dict[str, Any], user_id: str) -> str:
    logger.info(f"Iniciando reporte '{report_type}'")
    db = SessionLocal()
    
    try:
        # 1. Rutas
        report_id = uuid.uuid4()
        report_dir = UPLOAD_DIR / "reportes"
        report_dir.mkdir(parents=True, exist_ok=True)
        formato = filters.get("formato", "csv").lower()
        report_path = report_dir / f"{report_id}.{formato}"

        # 2. PARSEO DE FECHAS (Arreglo Pylance)
        # Convertimos los strings ISO que llegaron de Celery de vuelta a objetos date
        fecha_inicio_str = filters.get("fecha_inicio")
        fecha_fin_str = filters.get("fecha_fin")
        
        f_inicio = datetime.strptime(fecha_inicio_str, "%Y-%m-%d").date() if fecha_inicio_str else None
        f_fin = datetime.strptime(fecha_fin_str, "%Y-%m-%d").date() if fecha_fin_str else None

        # 3. OBTENER DATOS
        datos = reporte_service.obtener_datos(
            db, 
            tipo_reporte=report_type, 
            fecha_inicio=f_inicio, # Ahora sí enviamos objetos date (o None)
            fecha_fin=f_fin
        )

        # 4. ESCRIBIR ARCHIVO
        if formato == "csv":
            generar_csv(report_path, datos)
        elif formato == "pdf":
            generar_pdf(report_path, datos, f"Reporte de {report_type.capitalize()}")
        else:
            raise NotImplementedError(f"El formato {formato} aún no está implementado.")

        # 5. NOTIFICACIÓN
        nueva_notificacion = Notificacion(
            usuario_id=user_id,
            mensaje=f"Reporte de '{report_type}' ({formato.upper()}) generado. Disponible por 1 hora.",
            tipo="info",
            urgencia=0,
            referencia_id=report_id,
            referencia_tabla="reporte_generado"
        )
        db.add(nueva_notificacion)
        db.commit()

        # 6. AUTODESTRUCCIÓN
        celery_app.send_task("tasks.cleanup_report", args=[str(report_path)], countdown=3600)

        return "Reporte generado."

    except Exception as e:
        logger.error(f"Error reporte '{report_type}': {e}", exc_info=True)
        db.rollback()
        return "Error al generar reporte."
    finally:
        db.close()

# ==========================================
# FUNCIONES AUXILIARES DE GENERACIÓN
# ==========================================
def generar_csv(ruta_archivo: Path, datos: list):
    """Genera el archivo CSV con BOM para compatibilidad con Excel en Windows"""
    if not datos:
        with open(ruta_archivo, 'w', encoding='utf-8-sig') as f:
            f.write("No hay datos para este reporte.")
        return
    # ✅ utf-8-sig agrega el BOM que Excel necesita para leer tildes correctamente
    with open(ruta_archivo, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=datos[0].keys())
        writer.writeheader()
        writer.writerows(datos)


def generar_pdf(ruta_archivo: Path, datos: list, titulo: str):
    """Genera un archivo PDF. Compatilble con fpdf2 donde output() retorna bytes."""
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.add_page()
    
    # Título
    pdf.set_font("helvetica", "B", 16)
    pdf.cell(0, 10, titulo, align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)
    
    if not datos:
        pdf.set_font("helvetica", "", 12)
        pdf.cell(0, 10, "No hay datos para el rango seleccionado.")
        with open(ruta_archivo, "wb") as f:      # ✅ FIX
            f.write(pdf.output())
        return
        
    columnas = list(datos[0].keys())
    ancho_pagina = 277
    ancho_columna = ancho_pagina / len(columnas)
    
    # Encabezados
    pdf.set_font("helvetica", "B", 10)
    for col in columnas:
        pdf.cell(ancho_columna, 10, str(col), border=1, align="C")
    pdf.ln()
    
    # Filas
    pdf.set_font("helvetica", "", 9)
    for fila in datos:
        for col in columnas:
            valor = str(fila.get(col, ""))[:30]
            pdf.cell(ancho_columna, 8, valor, border=1)
        pdf.ln()
    
    with open(ruta_archivo, "wb") as f:          # ✅ FIX
        f.write(pdf.output())
