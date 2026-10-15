from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import select, func
from fastapi import HTTPException, status

from app.models.estado_equipo import EstadoEquipo
from app.models.equipo import Equipo
from app.schemas.estado_equipo import EstadoEquipoCreate, EstadoEquipoUpdate
from app.core.equipment_states import SYSTEM_STATE_CODES

from .base_service import BaseService


class EstadoEquipoService(BaseService[EstadoEquipo, EstadoEquipoCreate, EstadoEquipoUpdate]):
    """
    Servicio para gestionar los Estados de Equipo (catálogo).
    Las operaciones CUD (Create, Update, Delete) heredadas de BaseService
    NO realizan commit. El commit debe ser manejado en la capa de la ruta.
    """

    def get_by_nombre(self, db: Session, nombre: str) -> Optional[EstadoEquipo]:
        """Busca un estado de equipo por su nombre."""
        statement = select(self.model).where(self.model.nombre == nombre)
        result = db.execute(statement)
        return result.scalar_one_or_none()

    def update(self, db: Session, *, db_obj: EstadoEquipo, obj_in):
        values = obj_in if isinstance(obj_in, dict) else obj_in.model_dump(exclude_unset=True)
        if 'codigo' in values:
            raise HTTPException(409, 'El código operativo del estado no puede modificarse.')
        if db_obj.codigo in SYSTEM_STATE_CODES and any(key in values and values[key] != getattr(db_obj, key) for key in ('permite_movimientos', 'es_estado_final')):
            raise HTTPException(409, 'Las reglas de los estados del sistema están protegidas. Puedes modificar su nombre, descripción y color.')
        return super().update(db, db_obj=db_obj, obj_in=obj_in)

    # Ejemplo de cómo se podría sobreescribir create con validación adicional
    # def create(self, db: Session, *, obj_in: EstadoEquipoCreate) -> EstadoEquipo:
    #     existing = self.get_by_nombre(db, nombre=obj_in.nombre)
    #     if existing:
    #         raise HTTPException(
    #             status_code=status.HTTP_409_CONFLICT, # 409 para conflicto con recurso existente
    #             detail="Ya existe un estado de equipo con este nombre."
    #         )
    #     # Llamada al método base que NO hace commit
    #     db_obj = super().create(db, obj_in=obj_in)
    #     # El commit se haría en la ruta
    #     return db_obj

    # Ejemplo de cómo se podría sobreescribir update con validación adicional
    # def update(self, db: Session, *, db_obj: EstadoEquipo, obj_in: EstadoEquipoUpdate) -> EstadoEquipo:
    #     if obj_in.nombre: # Si se intenta cambiar el nombre
    #         existing_with_new_name = self.get_by_nombre(db, nombre=obj_in.nombre)
    #         if existing_with_new_name and existing_with_new_name.id != db_obj.id:
    #             raise HTTPException(
    #                 status_code=status.HTTP_409_CONFLICT,
    #                 detail="Ya existe otro estado de equipo con el nuevo nombre especificado."
    #             )
    #     # Llamada al método base que NO hace commit
    #     updated_db_obj = super().update(db, db_obj=db_obj, obj_in=obj_in)
    #     # El commit se haría en la ruta
    #     return updated_db_obj
        
    # Lógica para verificar si un estado se puede borrar (ej: si tiene equipos asociados)
    # Esta lógica se ejecutaría ANTES de llamar a super().remove()
    def check_if_can_be_deleted(self, db: Session, estado_id: UUID):
        """
        Verifica si un estado de equipo puede ser eliminado.
        Lanza HTTPException si no se puede eliminar.
        """
        stmt_count_equipos = select(func.count(Equipo.id)).where(Equipo.estado_id == estado_id)
        count_equipos = db.execute(stmt_count_equipos).scalar_one()
        
        if count_equipos > 0:
            db_obj = self.get(db, id=estado_id) # Para obtener el nombre para el mensaje
            estado_nombre = db_obj.nombre if db_obj else f"ID {estado_id}"
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"El estado '{estado_nombre}' está en uso por {count_equipos} equipo(s) y no puede ser eliminado."
            )
        estado = self.get(db, id=estado_id)
        if estado and estado.codigo in SYSTEM_STATE_CODES:
            raise HTTPException(409, 'No se puede eliminar un estado necesario para los flujos del sistema.')

    def remove(self, db: Session, *, id: UUID) -> EstadoEquipo:
        self.check_if_can_be_deleted(db, estado_id=id)
        return super().remove(db, id=id)
    
    # El método remove de BaseService ya no hace commit.
    # Si se necesita lógica de pre-eliminación, se puede sobreescribir remove:
    # def remove(self, db: Session, *, id: UUID) -> EstadoEquipo:
    #     self.check_if_can_be_deleted(db, estado_id=id) # Validar primero
    #     # Llamada al método base que NO hace commit
    #     deleted_obj = super().remove(db, id=id)
    #     # El commit se haría en la ruta
    #     return deleted_obj


estado_equipo_service = EstadoEquipoService(EstadoEquipo)
