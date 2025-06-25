from typing import List, Optional, Union, Dict, Any
from uuid import UUID
import logging

from sqlalchemy.orm import Session
from sqlalchemy import func, select
from fastapi import HTTPException, status

from app.models.rol import Rol
from app.models.permiso import Permiso
from app.models.usuario import Usuario
from app.schemas.rol import RolCreate, RolUpdate
from .base_service import BaseService
from .permiso import permiso_service

logger = logging.getLogger(__name__)

class RolService(BaseService[Rol, RolCreate, RolUpdate]):
    """
    Servicio para gestionar Roles y sus Permisos asociados.
    """

    def get_by_name(self, db: Session, *, name: str) -> Optional[Rol]:
        statement = select(self.model).where(self.model.nombre == name)
        result = db.execute(statement)
        return result.scalar_one_or_none()

    def create(self, db: Session, *, obj_in: RolCreate) -> Rol:
        """
        Crea un nuevo rol y le asigna los permisos especificados.
        NO realiza db.commit().
        """
        logger.debug(f"Intentando crear rol con nombre: {obj_in.nombre}")
        existing_rol = self.get_by_name(db, name=obj_in.nombre)
        if existing_rol:
            logger.warning(f"Intento de crear rol con nombre duplicado: {obj_in.nombre}")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Ya existe un rol con el nombre '{obj_in.nombre}'.",
            )

        rol_data = obj_in.model_dump(exclude={"permiso_ids"})
        db_rol = self.model(**rol_data)

        permisos_a_asignar: List[Permiso] = []
        if obj_in.permiso_ids:
            logger.debug(f"Asignando permisos {obj_in.permiso_ids} al nuevo rol {obj_in.nombre}")
            for permiso_id_val in obj_in.permiso_ids:
                permiso = permiso_service.get(db, id=permiso_id_val)
                if not permiso:
                    logger.error(f"Permiso con ID {permiso_id_val} no encontrado al crear rol.")
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Permiso con ID {permiso_id_val} no encontrado.",
                    )
                permisos_a_asignar.append(permiso)
        
        db_rol.permisos = permisos_a_asignar
        db.add(db_rol)
        logger.info(f"Rol '{db_rol.nombre}' preparado para ser creado con {len(permisos_a_asignar)} permiso(s).")
        return db_rol

    def update(
        self,
        db: Session,
        *,
        db_obj: Rol,
        obj_in: Union[RolUpdate, Dict[str, Any]]
    ) -> Rol:
        """
        Actualiza un rol existente, incluyendo sus permisos.
        NO realiza db.commit().
        """
        update_data_dict = obj_in if isinstance(obj_in, dict) else obj_in.model_dump(exclude_unset=True)
        rol_id = db_obj.id

        logger.debug(f"Intentando actualizar rol ID {rol_id} con datos: {update_data_dict}")

        if "nombre" in update_data_dict and update_data_dict["nombre"] != db_obj.nombre:
            logger.debug(f"Validando nuevo nombre '{update_data_dict['nombre']}' para rol ID {rol_id}")
            existing_rol = self.get_by_name(db, name=update_data_dict["nombre"])
            if existing_rol and existing_rol.id != rol_id:
                logger.warning(f"Conflicto de nombre al actualizar rol ID {rol_id} a '{update_data_dict['nombre']}'. Ya existe.")
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Ya existe otro rol con el nombre '{update_data_dict['nombre']}'.",
                )

        permiso_ids_actualizar = update_data_dict.pop("permiso_ids", None)

        db_obj = super().update(db, db_obj=db_obj, obj_in=update_data_dict)
        logger.debug(f"Campos simples del rol ID {rol_id} preparados para actualización.")

        if permiso_ids_actualizar is not None:
            logger.debug(f"Actualizando permisos para rol ID {rol_id} con IDs: {permiso_ids_actualizar}")
            permisos_a_asignar: List[Permiso] = []
            if permiso_ids_actualizar:
                for permiso_id_val in permiso_ids_actualizar:
                    permiso = permiso_service.get(db, id=permiso_id_val)
                    if not permiso:
                        logger.error(f"Permiso con ID {permiso_id_val} no encontrado al actualizar rol {rol_id}.")
                        raise HTTPException(
                            status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Permiso con ID {permiso_id_val} no encontrado al actualizar rol.",
                        )
                    permisos_a_asignar.append(permiso)
            
            db_obj.permisos = permisos_a_asignar
            db.add(db_obj)
            logger.info(f"Permisos para rol ID {rol_id} preparados para actualización ({len(permisos_a_asignar)} permisos).")
        
        logger.info(f"Rol ID {rol_id} ('{db_obj.nombre}') preparado para ser actualizado.")
        return db_obj

    def remove(self, db: Session, *, id: Union[UUID, int]) -> Rol:
        """
        Elimina un rol. Verifica primero si tiene usuarios asignados.
        NO realiza db.commit().
        """
        logger.debug(f"Intentando eliminar rol ID: {id}")
        db_obj = self.get_or_404(db, id=id)
        
        user_count_stmt = select(func.count(Usuario.id)).where(Usuario.rol_id == id)
        user_count = db.execute(user_count_stmt).scalar_one()

        if user_count > 0:
            logger.warning(f"Intento de eliminar rol '{db_obj.nombre}' (ID: {id}) que tiene {user_count} usuario(s) asignado(s).")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"No se puede eliminar el rol '{db_obj.nombre}' porque tiene {user_count} usuario(s) asignado(s). Reasígnelos primero."
            )
        
        deleted_obj = super().remove(db, id=id)
        logger.info(f"Rol '{deleted_obj.nombre}' (ID: {id}) preparado para ser eliminado.")
        return deleted_obj

rol_service = RolService(Rol)
