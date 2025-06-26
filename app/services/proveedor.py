import logging
from typing import Optional, List, Union, Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import select, exc

from fastapi.encoders import jsonable_encoder
from fastapi import HTTPException, status
from pydantic import HttpUrl

from app.models.proveedor import Proveedor
from app.schemas.proveedor import ProveedorCreate, ProveedorUpdate

from .base_service import BaseService

logger = logging.getLogger(__name__)

class ProveedorService(BaseService[Proveedor, ProveedorCreate, ProveedorUpdate]):

    def get_by_name(self, db: Session, *, nombre: str) -> Optional[Proveedor]:
        """Obtiene un proveedor por su nombre."""
        statement = select(self.model).where(self.model.nombre == nombre)
        result = db.execute(statement)
        return result.scalar_one_or_none()

    def get_by_rnc(self, db: Session, *, rnc: str) -> Optional[Proveedor]:
        if not rnc:
            return None
        statement = select(self.model).where(self.model.rnc == rnc)
        result = db.execute(statement)
        return result.scalar_one_or_none()

    def create(self, db: Session, *, obj_in: ProveedorCreate) -> Proveedor:
        """
        Crea un nuevo proveedor.
        Convierte HttpUrl a string antes de la inserción en BD.
        """
        logger.debug(f"Validando unicidad para nuevo proveedor con nombre: {obj_in.nombre}, RNC: {obj_in.rnc}")
        if self.get_by_name(db, nombre=obj_in.nombre):
             logger.warning(f"Intento de crear proveedor con nombre duplicado: {obj_in.nombre}")
             raise HTTPException(
                 status_code=status.HTTP_409_CONFLICT,
                 detail=f"Ya existe un proveedor con el nombre '{obj_in.nombre}'.",
             )

        if obj_in.rnc and self.get_by_rnc(db, rnc=obj_in.rnc):
             logger.warning(f"Intento de crear proveedor con RNC duplicado: {obj_in.rnc}")
             raise HTTPException(
                 status_code=status.HTTP_409_CONFLICT,
                 detail=f"Ya existe un proveedor con el RNC '{obj_in.rnc}'.",
             )

        # ===== INICIO DE LA CORRECCIÓN =====
        # jsonable_encoder convierte todos los tipos de Pydantic, incluyendo HttpUrl, a tipos nativos de Python.
        obj_in_data = jsonable_encoder(obj_in)
        
        # Creamos la instancia del modelo SQLAlchemy directamente con el diccionario de datos ya procesado.
        db_obj = self.model(**obj_in_data)
        db.add(db_obj)
        # El commit y refresh se manejan en la ruta de la API
        # ===== FIN DE LA CORRECCIÓN =====
        
        logger.info(f"Proveedor '{db_obj.nombre}' preparado para ser creado.")
        return db_obj


    def update(
        self, db: Session, *, db_obj: Proveedor, obj_in: Union[ProveedorUpdate, Dict[str, Any]]
    ) -> Proveedor:
        """
        Actualiza un proveedor existente.
        Añade validación de unicidad para nombre y RNC si se actualizan.
        NO realiza db.commit(). El commit debe ser manejado por el llamador.
        """
        update_data = obj_in if isinstance(obj_in, dict) else obj_in.model_dump(exclude_unset=True)
        current_id = db_obj.id

        logger.debug(f"Validando unicidad para actualización de proveedor ID {current_id}")

        if 'nombre' in update_data and update_data['nombre'] != db_obj.nombre:
             if self.get_by_name(db, nombre=update_data['nombre']):
                 logger.warning(f"Conflicto de nombre al actualizar proveedor ID {current_id} a '{update_data['nombre']}'. Ya existe.")
                 raise HTTPException(
                     status_code=status.HTTP_409_CONFLICT,
                     detail=f"Ya existe otro proveedor con el nombre '{update_data['nombre']}'."
                 )

        if 'rnc' in update_data and update_data['rnc'] and update_data['rnc'] != db_obj.rnc:
             if self.get_by_rnc(db, rnc=update_data['rnc']):
                 logger.warning(f"Conflicto de RNC al actualizar proveedor ID {current_id} a '{update_data['rnc']}'. Ya existe.")
                 raise HTTPException(
                     status_code=status.HTTP_409_CONFLICT,
                     detail=f"Ya existe otro proveedor con el RNC '{update_data['rnc']}'."
                 )
        
        # Convertir HttpUrl a string si viene en la actualización
        if 'sitio_web' in update_data and isinstance(update_data['sitio_web'], HttpUrl):
            update_data['sitio_web'] = str(update_data['sitio_web'])

        updated_db_obj = super().update(db, db_obj=db_obj, obj_in=update_data)
        logger.info(f"Proveedor ID {current_id} preparado para ser actualizado.")
        return updated_db_obj

proveedor_service = ProveedorService(Proveedor)
