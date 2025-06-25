import uuid
from typing import TYPE_CHECKING, List, Optional
from datetime import datetime

from sqlalchemy import Column, String, Text, DateTime, func
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base
# --- Añadido: Importar el modelo de asociación ---
from .rol_permiso import RolPermiso # <-- IMPORTANTE
# --- Fin Añadido ---


if TYPE_CHECKING:
    from .rol import Rol
    # from .rol_permiso import RolPermiso # Ya no es solo para TYPE_CHECKING


class Permiso(Base):
    __tablename__ = "permisos"
    # __table_args__ = {"schema": "control_equipos"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    descripcion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    roles: Mapped[List["Rol"]] = relationship(
        "Rol",
        # --- CORRECCIÓN: Usar el objeto Table explícito ---
        secondary=RolPermiso.__table__, # <-- CORREGIDO
        # -------------------------------------------------
        back_populates="permisos",
        lazy="selectin"
    )

    # Opcional: Relación con la tabla de asociación RolPermiso si necesitas navegar desde Permiso
    # rol_permiso_associations: Mapped[List["RolPermiso"]] = relationship(
    #    "RolPermiso", back_populates="permiso" # Asegúrate que 'permiso' exista en RolPermiso si activas esto
    # )

    def __repr__(self) -> str:
        return f"<Permiso(id={self.id}, nombre='{self.nombre}')>"

    # Relación (Muchos-a-Muchos con Rol a través de roles_permisos)
    # 'roles' será el atributo para acceder a los roles que tienen este permiso.
    # 'back_populates' debe coincidir con el nombre del atributo en el modelo Rol.
    # 'secondary' apunta a la tabla de asociación (incluyendo schema).
    # 'lazy="selectin"' carga los roles relacionados eficientemente cuando se accede al atributo.
    # Esta relación es opcional definirla aquí si solo navegas de Rol -> Permiso
    # roles = relationship(
    #     "Rol",
    #     secondary="control_equipos.roles_permisos",
    #     back_populates="permisos",
    #     lazy="selectin"
    # )
