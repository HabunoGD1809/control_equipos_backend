import logging
from sqlalchemy.orm import Session
from datetime import date
from typing import List, Dict, Any, Optional

from app.models.equipo import Equipo
from app.models.mantenimiento import Mantenimiento
from app.models.movimiento import Movimiento
from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)

class ReporteService:
    def obtener_datos(
        self, 
        db: Session, 
        tipo_reporte: str, 
        fecha_inicio: Optional[date], 
        fecha_fin: Optional[date]
    ) -> List[Dict[str, Any]]:
        """
        Fábrica de reportes. Retorna una lista de diccionarios lista para convertirse en CSV/PDF.
        """
        logger.info(f"Generando datos para reporte: {tipo_reporte}")
        
        if tipo_reporte == "equipos":
            return self._reporte_equipos(db, fecha_inicio, fecha_fin)
        elif tipo_reporte == "mantenimientos":
            return self._reporte_mantenimientos(db, fecha_inicio, fecha_fin)
        elif tipo_reporte == "kardex":
            # Aquí pondrías la consulta a InventarioStock
            return [{"Mensaje": "Reporte de Kardex en desarrollo"}]
        elif tipo_reporte == "movimientos":
            return self._reporte_movimientos(db, fecha_inicio, fecha_fin)
        elif tipo_reporte == "auditoria":
            return self._reporte_auditoria(db, fecha_inicio, fecha_fin)
        else:
            return [{"Error": "Tipo de reporte desconocido"}]

    def _reporte_equipos(self, db: Session, f_inicio: Optional[date], f_fin: Optional[date]) -> List[Dict[str, Any]]:
        equipos = db.query(Equipo).all()
        return [
            {"ID": str(e.id), "Nombre": e.nombre, "Serie": e.numero_serie, "Estado": e.estado.nombre if e.estado else "N/A"} 
            for e in equipos
        ]

    def _reporte_mantenimientos(self, db: Session, f_inicio: Optional[date], f_fin: Optional[date]) -> List[Dict[str, Any]]:
        mants = db.query(Mantenimiento).all() 
        return [
            {
                "Equipo": m.equipo.nombre if m.equipo else "N/A", 
                "Fecha Prog.": str(m.fecha_programada) if m.fecha_programada else "N/A", 
                "Costo": float(m.costo_real) if m.costo_real else 0.0, # Casteamos Decimal a float para el PDF/CSV
                "Estado": m.estado
            } 
            for m in mants
        ]

    def _reporte_movimientos(self, db: Session, f_inicio: Optional[date], f_fin: Optional[date]) -> List[Dict[str, Any]]:
        movs = db.query(Movimiento).all()
        return [
            {
                "Equipo": m.equipo.nombre if m.equipo else "N/A", 
                "Tipo": m.tipo_movimiento, 
                "Fecha": str(m.fecha_hora), 
                "Usuario": m.usuario_registrador.nombre_usuario if m.usuario_registrador else "Sistema"
            }
            for m in movs
        ]
        
    def _reporte_auditoria(self, db: Session, f_inicio: Optional[date], f_fin: Optional[date]) -> List[Dict[str, Any]]:
        logs = db.query(AuditLog).order_by(AuditLog.audit_timestamp.desc()).limit(100).all()
        return [
            {"Fecha": str(l.audit_timestamp), "Tabla": l.table_name, "Operacion": l.operation, "Usuario": l.username}
            for l in logs
        ]

reporte_service = ReporteService()
