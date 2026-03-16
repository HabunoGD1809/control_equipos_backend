from app.models.tecnico import Tecnico
from app.schemas.tecnico import TecnicoCreate, TecnicoUpdate
from .base_service import BaseService

class TecnicoService(BaseService[Tecnico, TecnicoCreate, TecnicoUpdate]):
    """
    Servicio para gestionar el catálogo de Técnicos de Mantenimiento (Internos y Externos).
    Hereda operaciones CRUD estándar de BaseService.
    """
    pass

tecnico_service = TecnicoService(Tecnico)
