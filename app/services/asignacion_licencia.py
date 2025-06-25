import logging
from typing import Optional, List, Union, Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import select
from fastapi import HTTPException, status

# Importar modelos y schemas
from app.models.asignacion_licencia import AsignacionLicencia
from app.schemas.asignacion_licencia import AsignacionLicenciaCreate, AsignacionLicenciaUpdate

# Importar la clase base y otros servicios necesarios
from .base_service import BaseService
from .licencia_software import licencia_software_service
from .equipo import equipo_service
from .usuario import usuario_service

logger = logging.getLogger(__name__)

class AsignacionLicenciaService(BaseService[AsignacionLicencia, AsignacionLicenciaCreate, AsignacionLicenciaUpdate]):
    """
    Servicio para gestionar las Asignaciones de Licencias.
    """

    def get_by_licencia_and_target(
        self, db: Session, *, licencia_id: UUID, equipo_id: Optional[UUID] = None, usuario_id: Optional[UUID] = None
    ) -> Optional[AsignacionLicencia]:
        """Verifica si existe una asignación específica para una licencia a un equipo o usuario."""
        logger.debug(f"Buscando asignación existente para Licencia ID: {licencia_id}, Equipo ID: {equipo_id}, Usuario ID: {usuario_id}")
        statement = select(self.model).where(self.model.licencia_id == licencia_id)
        if equipo_id:
            statement = statement.where(self.model.equipo_id == equipo_id)
        elif usuario_id:
             statement = statement.where(self.model.usuario_id == usuario_id)
        else:
            logger.warning("get_by_licencia_and_target llamado sin equipo_id ni usuario_id.")
            return None

        result = db.execute(statement)
        return result.scalar_one_or_none()

    def create(self, db: Session, *, obj_in: AsignacionLicenciaCreate) -> AsignacionLicencia:
        """
        Crea una nueva asignación, validando disponibilidad y FKs.
        NO realiza db.commit().
        """
        logger.debug(f"Intentando crear asignación para Licencia ID: {obj_in.licencia_id} -> Equipo ID: {obj_in.equipo_id}, Usuario ID: {obj_in.usuario_id}")

        if not (obj_in.equipo_id or obj_in.usuario_id) or (obj_in.equipo_id and obj_in.usuario_id):
             logger.warning("Intento de crear asignación sin un único target (equipo o usuario).")
             raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="La asignación debe ser a un equipo O a un usuario, no ambos o ninguno.")

        licencia = licencia_software_service.get(db, id=obj_in.licencia_id)
        if not licencia:
            logger.error(f"Licencia con ID {obj_in.licencia_id} no encontrada al crear asignación.")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Licencia con ID {obj_in.licencia_id} no encontrada.")

        if obj_in.equipo_id:
              equipo = equipo_service.get(db, id=obj_in.equipo_id)
              if not equipo:
                   logger.error(f"Equipo con ID {obj_in.equipo_id} no encontrado al crear asignación.")
                   raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Equipo con ID {obj_in.equipo_id} no encontrado.")
              if self.get_by_licencia_and_target(db, licencia_id=obj_in.licencia_id, equipo_id=obj_in.equipo_id):
                   logger.warning(f"Licencia ID {obj_in.licencia_id} ya asignada al equipo ID {obj_in.equipo_id}.")
                   raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Esta licencia ya está asignada a este equipo.")

        if obj_in.usuario_id:
              usuario = usuario_service.get(db, id=obj_in.usuario_id)
              if not usuario:
                   logger.error(f"Usuario con ID {obj_in.usuario_id} no encontrado al crear asignación.")
                   raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Usuario con ID {obj_in.usuario_id} no encontrado.")
              if self.get_by_licencia_and_target(db, licencia_id=obj_in.licencia_id, usuario_id=obj_in.usuario_id):
                   logger.warning(f"Licencia ID {obj_in.licencia_id} ya asignada al usuario ID {obj_in.usuario_id}.")
                   raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Esta licencia ya está asignada a este usuario.")

        if licencia.cantidad_disponible is None or licencia.cantidad_disponible <= 0:
              logger.warning(f"No hay licencias disponibles para '{licencia.software_info.nombre if licencia.software_info else 'N/A'}' (Licencia ID: {licencia.id}). Disponibles: {licencia.cantidad_disponible}")
              raise HTTPException(
                  status_code=status.HTTP_409_CONFLICT,
                  detail=f"No hay licencias disponibles para '{licencia.software_info.nombre if licencia.software_info else 'N/A'}' (Licencia ID: {licencia.id})."
              )

        db_asignacion = super().create(db, obj_in=obj_in)
        logger.info(f"Asignación de Licencia ID {db_asignacion.licencia_id} para target Equipo ID {db_asignacion.equipo_id}/Usuario ID {db_asignacion.usuario_id} preparada para ser creada.")
        return db_asignacion

    def update(
        self,
        db: Session,
        *,
        db_obj: AsignacionLicencia,
        obj_in: Union[AsignacionLicenciaUpdate, Dict[str, Any]]
    ) -> AsignacionLicencia:
        """
        Actualiza campos limitados de una asignación (ej. instalado, notas).
        NO realiza db.commit().
        """
        update_data = obj_in if isinstance(obj_in, dict) else obj_in.model_dump(exclude_unset=True)
        asignacion_id = db_obj.id
        logger.debug(f"Intentando actualizar asignación de licencia ID {asignacion_id} con datos: {update_data}")
        
        allowed_updates = {"fecha_instalacion", "notas", "instalado"}
        filtered_update_data = {k: v for k, v in update_data.items() if k in allowed_updates}

        if not filtered_update_data:
            logger.info(f"No hay campos válidos para actualizar en asignación ID {asignacion_id}. Devolviendo objeto sin cambios.")
            return db_obj 

        updated_db_asignacion = super().update(db, db_obj=db_obj, obj_in=filtered_update_data)
        logger.info(f"Asignación de licencia ID {asignacion_id} preparada para ser actualizada.")
        return updated_db_asignacion

    def remove(self, db: Session, *, id: Union[UUID, int]) -> AsignacionLicencia:
        """
        Elimina una asignación de licencia.
        NO realiza db.commit().
        """
        logger.debug(f"Intentando eliminar asignación de licencia ID: {id}")
        deleted_obj = super().remove(db, id=id)
        logger.warning(f"Asignación de licencia ID {id} (para Licencia ID: {deleted_obj.licencia_id}) preparada para ser eliminada.")
        return deleted_obj

    def get_multi_by_licencia(self, db: Session, *, licencia_id: UUID, skip: int = 0, limit: int = 100) -> List[AsignacionLicencia]:
        logger.debug(f"Listando asignaciones para Licencia ID: {licencia_id} (skip: {skip}, limit: {limit}).")
        statement = select(self.model).where(self.model.licencia_id == licencia_id).order_by(self.model.fecha_asignacion.desc()).offset(skip).limit(limit)
        result = db.execute(statement)
        return list(result.scalars().all())

    def get_multi_by_equipo(self, db: Session, *, equipo_id: UUID, skip: int = 0, limit: int = 100) -> List[AsignacionLicencia]:
        logger.debug(f"Listando asignaciones para Equipo ID: {equipo_id} (skip: {skip}, limit: {limit}).")
        statement = select(self.model).where(self.model.equipo_id == equipo_id).order_by(self.model.fecha_asignacion.desc()).offset(skip).limit(limit)
        result = db.execute(statement)
        return list(result.scalars().all())

    def get_multi_by_usuario(self, db: Session, *, usuario_id: UUID, skip: int = 0, limit: int = 100) -> List[AsignacionLicencia]:
        logger.debug(f"Listando asignaciones para Usuario ID: {usuario_id} (skip: {skip}, limit: {limit}).")
        statement = select(self.model).where(self.model.usuario_id == usuario_id).order_by(self.model.fecha_asignacion.desc()).offset(skip).limit(limit)
        result = db.execute(statement)
        return list(result.scalars().all())

asignacion_licencia_service = AsignacionLicenciaService(AsignacionLicencia)
