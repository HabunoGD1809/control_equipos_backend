import logging
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union
from uuid import UUID

from fastapi import HTTPException, status
from pydantic import BaseModel, HttpUrl # Asegúrate que HttpUrl esté importado si lo usas aquí

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

        **Parámetros**

        * `model`: Clase del modelo SQLAlchemy
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
        statement = select(self.model).offset(skip).limit(limit)
        result = db.execute(statement)
        return list(result.scalars().all()) # Convertir a lista explícitamente

    def get_count(self, db: Session) -> int:
        """Cuenta el número total de registros para el modelo."""
        count_query = select(func.count(self.model.id)) # type: ignore[attr-defined]
        count = db.execute(count_query).scalar_one_or_none() # Usar scalar_one_or_none para manejar 0 filas
        return count or 0

    def create(self, db: Session, *, obj_in: CreateSchemaType) -> ModelType:
        """
        Crea un nuevo registro.
        NO realiza db.commit(). El commit debe ser manejado por el llamador.
        """
        obj_in_data = obj_in.model_dump()
        db_obj = self.model(**obj_in_data)
        db.add(db_obj)
        # db.commit() # Eliminado
        # db.refresh(db_obj) # El refresh se hará después del commit en la ruta si es necesario
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
        Actualiza un objeto existente en la base de datos.
        NO realiza db.commit(). El commit debe ser manejado por el llamador.
        """
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            # Asegurar que exclude_unset=True para no sobrescribir campos no enviados con None
            update_data = obj_in.model_dump(exclude_unset=True) 

        obj_id = getattr(db_obj, 'id', 'N/A') # type: ignore[attr-defined]
        logger.debug(f"Actualizando {self.model.__name__} ID {obj_id} con datos: {update_data}")

        if update_data: # Solo proceder si hay datos para actualizar
            for field, value in update_data.items():
                if hasattr(db_obj, field):
                    # Convertir Pydantic HttpUrl a string si es necesario para el modelo SQLAlchemy
                    if isinstance(value, HttpUrl): 
                        setattr(db_obj, field, str(value))
                    else:
                        setattr(db_obj, field, value)
                else:
                     # Advertir si se intenta actualizar un campo que no existe en el modelo
                     logger.warning(f"Intento de actualizar campo '{field}' inexistente en modelo {self.model.__name__}")
            
            db.add(db_obj) # SQLAlchemy rastrea los cambios, add() asegura que esté en la sesión si es transitorio
            # db.commit() # Eliminado
            # db.refresh(db_obj) # El refresh se hará después del commit en la ruta si es necesario
            logger.info(f"Registro preparado para actualización en {self.model.__name__} (ID: {obj_id})")
        else:
             logger.info(f"No se proporcionaron datos para actualizar en {self.model.__name__} (ID: {obj_id})")

        return db_obj

    def remove(self, db: Session, *, id: Union[UUID, int]) -> ModelType:
        """
        Elimina un registro por ID.
        NO realiza db.commit(). El commit debe ser manejado por el llamador.
        """
        obj = self.get_or_404(db, id=id)
        obj_id_log = getattr(obj, 'id', 'N/A') # type: ignore[attr-defined]
        db.delete(obj)
        # db.commit() # Eliminado
        # No hacer db.refresh(obj) en un objeto eliminado.
        logger.warning(f"Registro preparado para eliminación de {self.model.__name__} (ID: {obj_id_log})")
        return obj
