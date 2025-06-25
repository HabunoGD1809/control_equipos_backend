import logging
from typing import Optional
from uuid import UUID # Importar UUID si los IDs son de este tipo

from sqlalchemy.orm import Session
from sqlalchemy import select

# Importar modelos y schemas necesarios
from app.models.permiso import Permiso
from app.schemas.permiso import PermisoCreate, PermisoUpdate

# Importar la clase base del servicio
from .base_service import BaseService # BaseService ya está modificado

logger = logging.getLogger(__name__)

class PermisoService(BaseService[Permiso, PermisoCreate, PermisoUpdate]):
    """
    Servicio para gestionar los Permisos.
    Hereda la funcionalidad CRUD básica de BaseService.
    Las operaciones CUD (Create, Update, Delete) heredadas de BaseService
    NO realizan commit. El commit debe ser manejado en la capa de la ruta.
    """

    def get_by_name(self, db: Session, *, name: str) -> Optional[Permiso]:
        """
        Obtiene un permiso por su nombre. (Ejemplo, si se necesitara)
        """
        statement = select(self.model).where(self.model.nombre == name) # Usar self.model
        result = db.execute(statement)
        return result.scalar_one_or_none()

    # Si se añadieran métodos create/update/delete específicos aquí,
    # deberían llamar a super().create(), super().update(), super().remove()
    # y no incluir db.commit() o db.refresh().

permiso_service = PermisoService(Permiso)
