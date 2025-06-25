import uuid
from typing import TYPE_CHECKING, Optional
from datetime import datetime

from sqlalchemy import Column, ForeignKey, DateTime, func, PrimaryKeyConstraint
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base

if TYPE_CHECKING:
    from .usuario import Usuario
    from .rol import Rol
    from .permiso import Permiso


class RolPermiso(Base):
    """
        Modelo ORM para la tabla de asociación 'roles_permisos'. 
    """
    __tablename__ = "roles_permisos"
    __table_args__ = (
        PrimaryKeyConstraint('rol_id', 'permiso_id', name='pk_roles_permisos'),
    )

    rol_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("roles.id", ondelete="CASCADE"), 
        primary_key=True
    )
    permiso_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("permisos.id", ondelete="CASCADE"), 
        primary_key=True
    )
    otorgado_por: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("usuarios.id", ondelete="SET NULL"), 
        nullable=True
    )
    fecha_otorgamiento: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )
    
    
    def __repr__(self) -> str:
        return f"<RolPermiso(rol_id={self.rol_id}, permiso_id={self.permiso_id})>"
    
    
    
    # --- Relaciones (Opcional, si necesitas navegar desde esta tabla) ---
    # rol: Mapped["Rol"] = relationship(back_populates="rol_permiso_associations")
    # permiso: Mapped["Permiso"] = relationship(back_populates="rol_permiso_associations")
    # otorgado_por_usuario: Mapped[Optional["Usuario"]] = relationship("Usuario")
