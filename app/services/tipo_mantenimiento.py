import logging
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import select

# Importar modelos y schemas
from app.models.tipo_mantenimiento import TipoMantenimiento
from app.schemas.tipo_mantenimiento import TipoMantenimientoCreate, TipoMantenimientoUpdate

# Importar la clase base del servicio
from .base_service import BaseService # BaseService ya está modificado

logger = logging.getLogger(__name__) # Configurar logger

class TipoMantenimientoService(BaseService[TipoMantenimiento, TipoMantenimientoCreate, TipoMantenimientoUpdate]):
    """
    Servicio para gestionar los Tipos de Mantenimiento (catálogo).
    Utiliza principalmente la funcionalidad CRUD de BaseService.
    Las operaciones CUD heredadas NO realizan commit.
    """

    def get_by_name(self, db: Session, *, name: str) -> Optional[TipoMantenimiento]:
        """Obtiene un tipo de mantenimiento por su nombre."""
        logger.debug(f"Buscando tipo de mantenimiento por nombre: '{name}'")
        statement = select(self.model).where(self.model.nombre == name) # type: ignore[attr-defined]
        result = db.execute(statement)
        return result.scalar_one_or_none()

    # Si se sobreescribieran create/update:
    # def create(self, db: Session, *, obj_in: TipoMantenimientoCreate) -> TipoMantenimiento:
    #     logger.debug(f"Intentando crear tipo de mantenimiento: {obj_in.nombre}")
    #     # ... (validaciones) ...
    #     db_obj = super().create(db, obj_in=obj_in) # No hace commit
    #     logger.info(f"Tipo de mantenimiento '{db_obj.nombre}' preparado para ser creado.")
    #     return db_obj

tipo_mantenimiento_service = TipoMantenimientoService(TipoMantenimiento)
