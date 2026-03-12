import logging
from uuid import UUID
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger(__name__)

class TimelineService:
    """
    Servicio encargado de leer la tabla de auditoría (audit_log) y 
    traducir los JSONs (old_data, new_data) a un Timeline de eventos legible por humanos.
    """
    def get_equipo_timeline(self, db: Session, equipo_id: UUID) -> List[Dict[str, Any]]:
        # La consulta definitiva: Busca en equipos, movimientos, mantenimientos y docs vinculados a este equipo.
        query = text("""
            SELECT audit_timestamp, table_name, operation, username, old_data, new_data
            FROM control_equipos.audit_log
            WHERE 
               (table_name = 'equipos' AND (new_data->>'id' = :eq_id OR old_data->>'id' = :eq_id))
               OR (table_name = 'movimientos' AND (new_data->>'equipo_id' = :eq_id OR old_data->>'equipo_id' = :eq_id))
               OR (table_name = 'mantenimiento' AND (new_data->>'equipo_id' = :eq_id OR old_data->>'equipo_id' = :eq_id))
               OR (table_name = 'documentacion' AND (new_data->>'equipo_id' = :eq_id OR old_data->>'equipo_id' = :eq_id))
            ORDER BY audit_timestamp DESC;
        """)

        result = db.execute(query, {"eq_id": str(equipo_id)}).fetchall()
        
        timeline_events = []
        
        for row in result:
            timestamp = row.audit_timestamp.strftime("%Y-%m-%d %H:%M")
            table = row.table_name
            op = row.operation
            user = row.username
            new_d = row.new_data or {}
            old_d = row.old_data or {}
            
            evento = {
                "fecha": timestamp,
                "usuario": user,
                "modulo": table.capitalize(),
                "icono": "activity", # Icono por defecto para el frontend
                "titulo": "Actividad registrada",
                "detalles": []
            }

            # --- TRADUCTOR DE JSON A LENGUAJE HUMANO ---
            if table == 'equipos':
                if op == 'INSERT':
                    evento["titulo"] = "Equipo registrado en el sistema"
                    evento["icono"] = "laptop"
                elif op == 'UPDATE':
                    evento["titulo"] = "Información del equipo actualizada"
                    evento["icono"] = "edit"
                    if old_d.get('estado_id') != new_d.get('estado_id'):
                        evento["detalles"].append("El estado interno del equipo cambió.")
                    if old_d.get('ubicacion_actual') != new_d.get('ubicacion_actual'):
                        evento["detalles"].append(f"Movido de '{old_d.get('ubicacion_actual')}' a '{new_d.get('ubicacion_actual')}'.")

            elif table == 'movimientos':
                evento["icono"] = "arrow-right-left"
                if op == 'INSERT':
                    tipo_mov = new_d.get('tipo_movimiento', 'Movimiento')
                    evento["titulo"] = f"Se inició un movimiento: {tipo_mov}"
                    evento["detalles"].append(f"Destino: {new_d.get('destino', 'N/A')}")
                elif op == 'UPDATE' and old_d.get('estado') != new_d.get('estado'):
                    evento["titulo"] = f"Movimiento actualizado a: {new_d.get('estado')}"
                    if new_d.get('observaciones'):
                        evento["detalles"].append(f"Nota: {new_d.get('observaciones')}")

            elif table == 'mantenimiento':
                evento["icono"] = "wrench"
                if op == 'INSERT':
                    evento["titulo"] = "Mantenimiento programado"
                    evento["detalles"].append(f"Técnico asignado: {new_d.get('tecnico_responsable')}")
                elif op == 'UPDATE' and old_d.get('estado') != new_d.get('estado'):
                    evento["titulo"] = f"Mantenimiento cambió a: {new_d.get('estado')}"

            elif table == 'documentacion':
                evento["icono"] = "file-text"
                if op == 'INSERT':
                    evento["titulo"] = f"Documento adjuntado: {new_d.get('titulo')}"

            # Añadimos el evento a la lista si generamos un título útil
            timeline_events.append(evento)

        return timeline_events

timeline_service = TimelineService()
