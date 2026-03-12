import logging
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union
from uuid import UUID

from fastapi import HTTPException, status
from pydantic import BaseModel, HttpUrl

from sqlalchemy.orm import Session
from sqlalchemy import func, select

from app.db.base import Base

ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)

logger = logging.getLogger(__name__)

class BaseService(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    def __init__(self, model: Type[ModelType]):
        """
        Servicio base con operaciones CRUD por defecto.
        Los métodos CUD (Create, Update, Delete) NO realizan commit.
        El commit debe ser manejado en la capa de la ruta (endpoint).
        """
        self.model = model

    def get(self, db: Session, id: Any) -> Optional[ModelType]:
        """Obtiene un registro por ID."""
        return db.get(self.model, id)

    def get_or_404(self, db: Session, id: Any) -> ModelType:
        """Obtiene un registro por ID o lanza 404 si no existe."""
        db_obj = self.get(db, id=id)
        if not db_obj:
             logger.warning(f"Registro no encontrado en {self.model.__name__} con ID: {id}")
             raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{self.model.__name__} con ID {id} no encontrado."
             )
        return db_obj

    def get_multi(
        self, db: Session, *, skip: int = 0, limit: int = 100
    ) -> List[ModelType]:
        """Obtiene múltiples registros con paginación."""
        # Se podría filtrar por is_active == True si la columna existe (soft deletes)
        statement = select(self.model).offset(skip).limit(limit)
        result = db.execute(statement)
        return list(result.scalars().all())

    def get_count(self, db: Session) -> int:
        """Cuenta el número total de registros para el modelo."""
        count_query = select(func.count(self.model.id)) # type: ignore[attr-defined]
        count = db.execute(count_query).scalar_one_or_none()
        return count or 0

    def create(self, db: Session, *, obj_in: CreateSchemaType) -> ModelType:
        """
        Crea un nuevo registro. NO realiza db.commit().
        """
        obj_in_data = obj_in.model_dump()
        db_obj = self.model(**obj_in_data)
        db.add(db_obj)
        logger.info(f"Nuevo registro preparado para creación en {self.model.__name__} con datos: {obj_in_data}")
        return db_obj

    def update(
        self,
        db: Session,
        *,
        db_obj: ModelType,
        obj_in: Union[UpdateSchemaType, Dict[str, Any]]
    ) -> ModelType:
        """
        Actualiza un objeto existente. NO realiza db.commit().
        """
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.model_dump(exclude_unset=True) 

        obj_id = getattr(db_obj, 'id', 'N/A')
        logger.debug(f"Actualizando {self.model.__name__} ID {obj_id} con datos: {update_data}")

        if update_data:
            for field, value in update_data.items():
                if hasattr(db_obj, field):
                    if isinstance(value, HttpUrl): 
                        setattr(db_obj, field, str(value))
                    else:
                        setattr(db_obj, field, value)
                else:
                     logger.warning(f"Intento de actualizar campo '{field}' inexistente en modelo {self.model.__name__}")
            
            db.add(db_obj)
            logger.info(f"Registro preparado para actualización en {self.model.__name__} (ID: {obj_id})")
        else:
             logger.info(f"No se proporcionaron datos para actualizar en {self.model.__name__} (ID: {obj_id})")

        return db_obj

    def remove(self, db: Session, *, id: Union[UUID, int]) -> ModelType:
        """
        Elimina un registro por ID.
        Intenta un Soft Delete si el modelo lo soporta, de lo contrario hace Hard Delete.
        """
        obj = self.get_or_404(db, id=id)
        obj_id_log = getattr(obj, 'id', 'N/A')
        
        # --- Soft Deletes ---
        if hasattr(obj, 'is_active'):
            setattr(obj, 'is_active', False)
            db.add(obj)
            logger.warning(f"Soft delete (is_active=False) en {self.model.__name__} (ID: {obj_id_log})")
        elif hasattr(obj, 'activo'):
            setattr(obj, 'activo', False)
            db.add(obj)
            logger.warning(f"Soft delete (activo=False) en {self.model.__name__} (ID: {obj_id_log})")
        else:
            # Fallback a Hard Delete si no existe la columna
            db.delete(obj)
            logger.warning(f"Hard delete en {self.model.__name__} (ID: {obj_id_log})")
            
        return obj
