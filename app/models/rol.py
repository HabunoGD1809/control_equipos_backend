import uuid
from typing import TYPE_CHECKING, List, Optional
from datetime import datetime

from sqlalchemy import Column, String, Text, DateTime, func, ForeignKey #, Table
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base
from .rol_permiso import RolPermiso 

if TYPE_CHECKING:
    from .permiso import Permiso
    from .usuario import Usuario

class Rol(Base):
    __tablename__ = "roles"
    # __table_args__ = {"schema": "control_equipos"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    descripcion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    permisos: Mapped[List["Permiso"]] = relationship(
        "Permiso",
        secondary=RolPermiso.__table__, 
        back_populates="roles",
        lazy="selectin"
    )

    usuarios: Mapped[List["Usuario"]] = relationship(
        "Usuario",
        back_populates="rol",
        lazy="selectin"
    )

    # Opcional: Relación con la tabla de asociación RolPermiso si necesitas navegar desde Rol
    # rol_permiso_associations: Mapped[List["RolPermiso"]] = relationship(
    #    "RolPermiso", back_populates="rol" # Asegúrate que 'rol' exista en RolPermiso si activas esto
    # )

    def __repr__(self) -> str:
        return f"<Rol(id={self.id}, nombre='{self.nombre}')>"
