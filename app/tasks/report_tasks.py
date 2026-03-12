import logging
import csv
import uuid
import traceback
import pandas as pd
from pathlib import Path
from typing import Dict, Any
from datetime import datetime, timezone

from app.worker import celery_app
from app.db.session import SessionLocal
from app.core.storage import UPLOAD_DIR
from app.models.notificacion import Notificacion
from app.models.reporte import Reporte
from app.services.reporte import reporte_service
from fpdf import FPDF

logger = logging.getLogger(__name__)

@celery_app.task(name="tasks.cleanup_report")
def task_cleanup_report(report_id_str: str, filepath: str):
    """
    Elimina el archivo físico y marca el registro en BD como expirado.
    """
    db = SessionLocal()
    try:
        path = Path(filepath)
        if path.exists():
            path.unlink()
            
        reporte = db.query(Reporte).filter(Reporte.id == report_id_str).first()
        if reporte:
            reporte.estado = "expirado"
            db.commit()
            logger.info(f"🗑️ Reporte expirado y eliminado: {filepath}")
    except Exception as e:
        db.rollback()
        logger.error(f"Error limpiando reporte {report_id_str}: {e}")
    finally:
        db.close()
    return True

@celery_app.task(name="tasks.generate_report")
def task_generate_report(report_id_str: str, report_type: str, filters: Dict[str, Any], formato: str, user_id: str) -> str:
    """
    Genera el archivo del reporte, actualiza la BD y notifica al usuario.
    """
    logger.info(f"Iniciando tarea de reporte: {report_id_str} ({report_type})")
    db = SessionLocal()
    
    try:
        # 1. Buscar y marcar como "procesando"
        reporte = db.query(Reporte).filter(Reporte.id == report_id_str).first()
        if not reporte:
            logger.error(f"Reporte {report_id_str} no encontrado en la base de datos.")
            return "Error: Registro no encontrado"
            
        reporte.estado = "procesando"
        db.commit()

        # 2. Configurar rutas
        report_dir = UPLOAD_DIR / "reportes"
        report_dir.mkdir(parents=True, exist_ok=True)
        formato = formato.lower()
        report_path = report_dir / f"{report_id_str}.{formato}"

        # 3. Parseo de Fechas
        fecha_inicio_str = filters.get("fecha_inicio")
        fecha_fin_str = filters.get("fecha_fin")
        f_inicio = datetime.strptime(fecha_inicio_str, "%Y-%m-%d").date() if fecha_inicio_str else None
        f_fin = datetime.strptime(fecha_fin_str, "%Y-%m-%d").date() if fecha_fin_str else None

        # 4. Obtener Datos
        datos = reporte_service.obtener_datos(
            db, 
            tipo_reporte=report_type, 
            fecha_inicio=f_inicio,
            fecha_fin=f_fin
        )

        # 5. Escribir Archivo Físico
        if formato == "csv":
            generar_csv(report_path, datos)
        elif formato == "pdf":
            generar_pdf(report_path, datos, f"Reporte de {report_type.capitalize()}")
        elif formato in ["excel", "xlsx"]:
            generar_excel(report_path, datos)
        else:
            raise NotImplementedError(f"El formato {formato} no está soportado.")

        # 6. Actualizar Registro del Reporte al tener Éxito
        archivo_size = report_path.stat().st_size if report_path.exists() else 0
        
        reporte.estado = "completado"
        reporte.archivo_path = str(report_path)
        reporte.archivo_size_bytes = archivo_size
        reporte.fecha_completado = datetime.now(timezone.utc)
        
        # 7. Crear Notificación
        nueva_notificacion = Notificacion(
            usuario_id=user_id,
            mensaje=f"Reporte de '{report_type}' ({formato.upper()}) generado con éxito.",
            tipo="info",
            urgencia=0,
            referencia_id=reporte.id, 
            referencia_tabla="reporte_generado"
        )
        db.add(nueva_notificacion)
        db.commit()

        # 8. Programar Autodestrucción (Ej: 24 horas = 86400 segundos)
        celery_app.send_task("tasks.cleanup_report", args=[report_id_str, str(report_path)], countdown=86400)

        return f"Reporte {report_id_str} completado."

    except Exception as e:
        db.rollback()
        logger.error(f"Error reporte '{report_type}': {e}", exc_info=True)
        
        # Intentamos obtener la sesión de nuevo en caso de que haya explotado arriba
        reporte = db.query(Reporte).filter(Reporte.id == report_id_str).first()
        if reporte:
            reporte.estado = "error"
            reporte.error_msg = traceback.format_exc()
            
            notif_error = Notificacion(
                usuario_id=user_id,
                mensaje=f"Ocurrió un error al generar tu reporte de '{report_type}'.",
                tipo="error",
                urgencia=2,
                referencia_id=reporte.id,
                referencia_tabla="reporte_generado"
            )
            db.add(notif_error)
            db.commit()
            
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
    with open(ruta_archivo, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=datos[0].keys())
        writer.writeheader()
        writer.writerows(datos)

def generar_pdf(ruta_archivo: Path, datos: list, titulo: str):
    """Genera un archivo PDF. Compatible con fpdf2 donde output() retorna bytes."""
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.add_page()
    
    # Título
    pdf.set_font("helvetica", "B", 16)
    pdf.cell(0, 10, titulo, align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)
    
    if not datos:
        pdf.set_font("helvetica", "", 12)
        pdf.cell(0, 10, "No hay datos para el rango seleccionado.")
        with open(ruta_archivo, "wb") as f:
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
    
    with open(ruta_archivo, "wb") as f:
        f.write(pdf.output())

def generar_excel(ruta_archivo: Path, datos: list):
    """Genera un archivo Excel (.xlsx) nativo usando pandas."""
    if not datos:
        df = pd.DataFrame([{"Aviso": "No hay datos para el rango seleccionado."}])
    else:
        df = pd.DataFrame(datos)
    
    # Exportamos a Excel usando el motor openpyxl
    df.to_excel(ruta_archivo, index=False, engine='openpyxl')
