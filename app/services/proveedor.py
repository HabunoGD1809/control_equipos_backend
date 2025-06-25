import logging 
from typing import Optional, List, Union, Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import select 

from fastapi import HTTPException, status

from app.models.proveedor import Proveedor
from app.schemas.proveedor import ProveedorCreate, ProveedorUpdate

from .base_service import BaseService # BaseService ya está modificado

logger = logging.getLogger(__name__) # Configurar logger

class ProveedorService(BaseService[Proveedor, ProveedorCreate, ProveedorUpdate]):

    def get_by_name(self, db: Session, *, nombre: str) -> Optional[Proveedor]:
        """Obtiene un proveedor por su nombre."""
        statement = select(self.model).where(self.model.nombre == nombre)
        result = db.execute(statement)
        return result.scalar_one_or_none() # Usar scalar_one_or_none

    def get_by_rnc(self, db: Session, *, rnc: str) -> Optional[Proveedor]:
        """Obtiene un proveedor por su RNC."""
        statement = select(self.model).where(self.model.rnc == rnc)
        result = db.execute(statement)
        return result.scalar_one_or_none() # Usar scalar_one_or_none

    def create(self, db: Session, *, obj_in: ProveedorCreate) -> Proveedor:
        """
        Crea un nuevo proveedor.
        Añade validación de unicidad para nombre y RNC antes de crear.
        NO realiza db.commit(). El commit debe ser manejado por el llamador.
        """
        logger.debug(f"Validando unicidad para nuevo proveedor con nombre: {obj_in.nombre}, RNC: {obj_in.rnc}")
        existing_by_name = self.get_by_name(db, nombre=obj_in.nombre)
        if existing_by_name:
             logger.warning(f"Intento de crear proveedor con nombre duplicado: {obj_in.nombre}")
             raise HTTPException(
                 status_code=status.HTTP_409_CONFLICT,
                 detail=f"Ya existe un proveedor con el nombre '{obj_in.nombre}'."
             )

        if obj_in.rnc: # Solo validar si RNC no es None o string vacío
             existing_by_rnc = self.get_by_rnc(db, rnc=obj_in.rnc)
             if existing_by_rnc:
                 logger.warning(f"Intento de crear proveedor con RNC duplicado: {obj_in.rnc}")
                 raise HTTPException(
                     status_code=status.HTTP_409_CONFLICT,
                     detail=f"Ya existe un proveedor con el RNC '{obj_in.rnc}'."
                 )
        
        # Usamos el método create de BaseService que ya no hace commit ni refresh
        # y maneja obj_in.model_dump() e instanciación del modelo.
        # Si quisiéramos mantener la instanciación manual aquí:
        # obj_in_data = obj_in.model_dump()
        # db_obj = self.model(**obj_in_data)
        # db.add(db_obj)
        # logger.info(f"Proveedor preparado para creación: {obj_in.nombre}")
        # return db_obj
        # Pero es mejor reutilizar BaseService.create:
        db_obj = super().create(db, obj_in=obj_in) # Esto añade a la sesión pero no hace commit
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
             existing_by_name = self.get_by_name(db, nombre=update_data['nombre'])
             if existing_by_name and existing_by_name.id != current_id:
                 logger.warning(f"Conflicto de nombre al actualizar proveedor ID {current_id} a '{update_data['nombre']}'. Ya existe.")
                 raise HTTPException(
                     status_code=status.HTTP_409_CONFLICT,
                     detail=f"Ya existe otro proveedor con el nombre '{update_data['nombre']}'."
                 )

        if 'rnc' in update_data and update_data['rnc'] and update_data['rnc'] != db_obj.rnc: # Asegurar que RNC no sea None o vacío
             existing_by_rnc = self.get_by_rnc(db, rnc=update_data['rnc'])
             if existing_by_rnc and existing_by_rnc.id != current_id:
                 logger.warning(f"Conflicto de RNC al actualizar proveedor ID {current_id} a '{update_data['rnc']}'. Ya existe.")
                 raise HTTPException(
                     status_code=status.HTTP_409_CONFLICT,
                     detail=f"Ya existe otro proveedor con el RNC '{update_data['rnc']}'."
                 )
        
        # Llama a super().update() que ya no hace commit ni refresh.
        # super().update() manejará la asignación de campos y db.add(db_obj).
        updated_db_obj = super().update(db, db_obj=db_obj, obj_in=update_data)
        logger.info(f"Proveedor ID {current_id} preparado para ser actualizado.")
        return updated_db_obj

    # get_multi, get, remove (que llama a get_or_404) son heredados de BaseService.
    # BaseService.remove ya no hace commit.

proveedor_service = ProveedorService(Proveedor)
