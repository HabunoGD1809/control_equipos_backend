import logging # Importar logging
from typing import Optional, Union, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import select
from fastapi import HTTPException, status

# Importar modelos y schemas
from app.models.software_catalogo import SoftwareCatalogo
from app.schemas.software_catalogo import SoftwareCatalogoCreate, SoftwareCatalogoUpdate

# Importar la clase base del servicio
from .base_service import BaseService # BaseService ya está modificado

logger = logging.getLogger(__name__) # Configurar logger

class SoftwareCatalogoService(BaseService[SoftwareCatalogo, SoftwareCatalogoCreate, SoftwareCatalogoUpdate]):
    """
    Servicio para gestionar el Catálogo de Software.
    Las operaciones CUD (Create, Update, Delete) heredadas o propias
    NO realizan commit. El commit debe ser manejado en la capa de la ruta.
    """

    def get_by_name_and_version(
        self, db: Session, *, name: str, version: Optional[str] = None
    ) -> Optional[SoftwareCatalogo]:
        """Obtiene un registro del catálogo por nombre y versión."""
        logger.debug(f"Buscando en catálogo de software por nombre='{name}', version='{version}'")
        statement = select(self.model).where(
            self.model.nombre == name,
            self.model.version == version # Comparación con None (SQL IS NULL) es manejada por SQLAlchemy
        )
        result = db.execute(statement)
        return result.scalar_one_or_none()

    def create(self, db: Session, *, obj_in: SoftwareCatalogoCreate) -> SoftwareCatalogo:
        """
        Crea un nuevo registro en el catálogo de software, validando unicidad.
        NO realiza db.commit().
        """
        logger.debug(f"Intentando crear entrada de catálogo SW: Nombre='{obj_in.nombre}', Versión='{obj_in.version}'")
        existing = self.get_by_name_and_version(db, name=obj_in.nombre, version=obj_in.version)
        if existing:
            logger.warning(f"Intento de crear entrada de catálogo SW duplicada: Nombre='{obj_in.nombre}', Versión='{obj_in.version or 'N/A'}'")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, # 409 para conflicto
                detail=f"Ya existe un software con el nombre '{obj_in.nombre}' y versión '{obj_in.version or 'N/A'}'.",
            )
        
        # super().create() ya no hace commit.
        db_catalogo_entry = super().create(db, obj_in=obj_in)
        logger.info(f"Entrada de catálogo SW '{db_catalogo_entry.nombre} v{db_catalogo_entry.version or 'N/A'}' preparada para ser creada.")
        return db_catalogo_entry

    def update(
        self,
        db: Session,
        *,
        db_obj: SoftwareCatalogo, # Entrada de catálogo existente de la BD
        obj_in: Union[SoftwareCatalogoUpdate, Dict[str, Any]]
    ) -> SoftwareCatalogo:
        """
        Actualiza un registro del catálogo, validando unicidad si cambian nombre/versión.
        NO realiza db.commit(). Llama a super().update() que tampoco lo hace.
        """
        update_data = obj_in if isinstance(obj_in, dict) else obj_in.model_dump(exclude_unset=True)
        catalogo_id = db_obj.id
        logger.debug(f"Intentando actualizar entrada de catálogo SW ID {catalogo_id} con datos: {update_data}")

        # Determinar el nombre y versión finales después de la posible actualización
        new_name = update_data.get("nombre", db_obj.nombre)
        new_version = update_data.get("version", db_obj.version) # Puede ser None

        # Validar unicidad solo si el nombre o la versión realmente van a cambiar a algo que podría existir
        if new_name != db_obj.nombre or new_version != db_obj.version:
            logger.debug(f"Validando nueva combinación nombre/versión: '{new_name}' / '{new_version}' para catálogo ID {catalogo_id}")
            existing = self.get_by_name_and_version(db, name=new_name, version=new_version)
            if existing and existing.id != catalogo_id: # Si existe y no es el mismo objeto
                logger.warning(f"Conflicto al actualizar catálogo SW ID {catalogo_id}. La combinación Nombre='{new_name}', Versión='{new_version or 'N/A'}' ya existe.")
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT, # 409 para conflicto
                    detail=f"Ya existe otro software con el nombre '{new_name}' y versión '{new_version or 'N/A'}'.",
                )
        
        # super().update() ya no hace commit.
        updated_db_catalogo = super().update(db, db_obj=db_obj, obj_in=update_data)
        logger.info(f"Entrada de catálogo SW ID {catalogo_id} ('{updated_db_catalogo.nombre} v{updated_db_catalogo.version or 'N/A'}') preparada para ser actualizada.")
        return updated_db_catalogo

    # El método remove es heredado de BaseService y ya no hace commit.
    # La FK en licencias_software (software_catalogo_id) es ON DELETE RESTRICT por defecto en PostgreSQL
    # si no se especifica otra cosa, lo que previene borrar si está en uso.
    # Esta restricción de BD es suficiente y será capturada por el manejador de IntegrityError en la ruta.

software_catalogo_service = SoftwareCatalogoService(SoftwareCatalogo)
