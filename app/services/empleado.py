from typing import Any, Dict, Union, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models.empleado import Empleado
from app.schemas.empleado import EmpleadoCreate, EmpleadoUpdate
from app.services.base_service import BaseService

class EmpleadoService(BaseService[Empleado, EmpleadoCreate, EmpleadoUpdate]):
    def search(self, db: Session, *, query: str, limit: int = 50) -> List[Empleado]:
        """Búsqueda rápida por nombre o email."""
        return (
            db.query(self.model)
            .filter(
                or_(
                    self.model.nombre_completo.ilike(f"%{query}%"),
                    self.model.email_corporativo.ilike(f"%{query}%")
                )
            )
            .limit(limit)
            .all()
        )

empleado_service = EmpleadoService(Empleado)
