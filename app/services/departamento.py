import logging
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.departamento import Departamento
from app.schemas.departamento import DepartamentoCreate, DepartamentoUpdate
from .base_service import BaseService

logger = logging.getLogger(__name__)

class DepartamentoService(BaseService[Departamento, DepartamentoCreate, DepartamentoUpdate]):
    def get_by_nombre(self, db: Session, *, nombre: str) -> Optional[Departamento]:
        statement = select(self.model).where(self.model.nombre == nombre)
        result = db.execute(statement)
        return result.scalar_one_or_none()

    def get_multi_active(self, db: Session, *, skip: int = 0, limit: int = 100) -> List[Departamento]:
        statement = select(self.model).where(self.model.is_active == True).order_by(self.model.nombre).offset(skip).limit(limit)
        result = db.execute(statement)
        return list(result.scalars().all())

departamento_service = DepartamentoService(Departamento)
