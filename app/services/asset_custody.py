"""Serialize physical assembly changes and preserve each serialized asset's custody."""
from uuid import UUID
from sqlalchemy import select, text, or_
from fastapi import HTTPException
from app.models.equipo import Equipo
from app.models.equipo_componente import EquipoComponente
from app.models.movimiento import Movimiento
from app.models.reserva_equipo import ReservaEquipo
from app.models.mantenimiento import Mantenimiento

PHYSICAL = ('componente', 'parte_de', 'accesorio')

def lock_topology(db):
    db.execute(text("SELECT pg_advisory_xact_lock(hashtext('control_equipos.asset_custody'))"))

def physical_group(db, root_id, *, allow_attached=False):
    lock_topology(db)
    if not allow_attached and db.scalar(select(EquipoComponente.id).where(EquipoComponente.equipo_componente_id == root_id, EquipoComponente.tipo_relacion.in_(PHYSICAL)).limit(1)):
        raise HTTPException(409, 'Este activo forma parte de otro equipo. Opere sobre el equipo principal o desvincule el componente primero.')
    ids = list(db.scalars(text("""WITH RECURSIVE members(id) AS (
        SELECT CAST(:root AS uuid) UNION
        SELECT ec.equipo_componente_id FROM control_equipos.equipo_componentes ec JOIN members m ON ec.equipo_padre_id=m.id WHERE ec.tipo_relacion IN ('componente','parte_de','accesorio')
    ) SELECT id FROM members"""), {'root': str(root_id)}))
    return list(db.scalars(select(Equipo).where(Equipo.id.in_(ids)).order_by(Equipo.id).with_for_update(of=Equipo).execution_options(populate_existing=True)).unique())

def ensure_free(db, members, *, exclude_maintenance=None):
    ids = [item.id for item in members]
    if not ids: return
    moving = db.scalar(select(Movimiento.id).where(Movimiento.equipo_id.in_(ids), or_(Movimiento.estado.in_(['Pendiente','Autorizado','En Proceso']), (Movimiento.tipo_movimiento == 'Salida Temporal') & (Movimiento.fecha_retorno.is_(None)) & (Movimiento.estado == 'Completado'))).limit(1))
    borrowed = db.scalar(select(ReservaEquipo.id).where(ReservaEquipo.equipo_id.in_(ids), ReservaEquipo.estado == 'En Curso').limit(1))
    repair_query = select(Mantenimiento.id).where(Mantenimiento.equipo_id.in_(ids), Mantenimiento.estado.in_(['En Proceso','Pausado','Requiere Piezas']))
    if exclude_maintenance: repair_query = repair_query.where(Mantenimiento.id != exclude_maintenance)
    repairing = db.scalar(repair_query.limit(1))
    if moving or borrowed or repairing:
        raise HTTPException(409, 'Un activo del conjunto tiene una entrega, préstamo o mantenimiento en curso.')

def snapshot(members, root_id):
    return {str(item.id): {'estado_id': str(item.estado_id), 'ubicacion_id': str(item.ubicacion_id) if item.ubicacion_id else None, 'empleado_id': str(item.empleado_asignado_id) if item.empleado_asignado_id else None, 'nombre': item.nombre, 'numero_serie': item.numero_serie, 'codigo_interno': item.codigo_interno} for item in members if item.id != root_id}

def propagate(db, root, saved, *, restore=False):
    if not saved: return
    ids = [UUID(value) for value in saved]
    members = list(db.scalars(select(Equipo).where(Equipo.id.in_(ids)).order_by(Equipo.id).with_for_update(of=Equipo).execution_options(populate_existing=True)).unique())
    if len(members) != len(saved): raise HTTPException(409, 'Faltan activos del conjunto; revise su historial antes de continuar.')
    for item in members:
        if restore:
            old = saved[str(item.id)]
            item.estado_id = UUID(old['estado_id'])
            item.ubicacion_id = UUID(old['ubicacion_id']) if old['ubicacion_id'] else None
            item.empleado_asignado_id = UUID(old['empleado_id']) if old['empleado_id'] else None
        else:
            item.estado_id = root.estado_id
            item.ubicacion_id = root.ubicacion_id
            item.empleado_asignado_id = root.empleado_asignado_id
        db.add(item)
