import logging
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import select

# Importar modelos y schemas
from app.models.tipo_documento import TipoDocumento
from app.schemas.tipo_documento import TipoDocumentoCreate, TipoDocumentoUpdate

# Importar la clase base del servicio
from .base_service import BaseService # BaseService ya está modificado

logger = logging.getLogger(__name__) # Configurar logger

class TipoDocumentoService(BaseService[TipoDocumento, TipoDocumentoCreate, TipoDocumentoUpdate]):
    """
    Servicio para gestionar los Tipos de Documento (catálogo).
    Utiliza principalmente la funcionalidad CRUD de BaseService.
    Las operaciones CUD heredadas NO realizan commit.
    """

    def get_by_name(self, db: Session, *, name: str) -> Optional[TipoDocumento]:
        """Obtiene un tipo de documento por su nombre."""
        logger.debug(f"Buscando tipo de documento por nombre: '{name}'")
        statement = select(self.model).where(self.model.nombre == name) # type: ignore[attr-defined]
        result = db.execute(statement)
        return result.scalar_one_or_none()

    # Si se sobreescribieran create/update:
    # def create(self, db: Session, *, obj_in: TipoDocumentoCreate) -> TipoDocumento:
    #     logger.debug(f"Intentando crear tipo de documento: {obj_in.nombre}")
    #     # ... (validaciones, ej. get_by_name) ...
    #     # if self.get_by_name(db, name=obj_in.nombre):
    #     #     raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Nombre ya existe.")
    #     db_obj = super().create(db, obj_in=obj_in) # No hace commit
    #     logger.info(f"Tipo de documento '{db_obj.nombre}' preparado para ser creado.")
    #     return db_obj

tipo_documento_service = TipoDocumentoService(TipoDocumento)
