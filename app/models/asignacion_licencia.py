import uuid
from typing import TYPE_CHECKING, Optional
from datetime import datetime

from sqlalchemy import (
    Column, ForeignKey, DateTime, func, Boolean, Text, UniqueConstraint, CheckConstraint
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base

if TYPE_CHECKING:
    from .licencia_software import LicenciaSoftware
    from .equipo import Equipo
    from .usuario import Usuario


class AsignacionLicencia(Base):
    __tablename__ = "asignaciones_licencia"
    __table_args__ = (
        UniqueConstraint('licencia_id', 'equipo_id', name='uq_asignacion_licencia_equipo'),
        UniqueConstraint('licencia_id', 'usuario_id', name='uq_asignacion_licencia_usuario'),
        CheckConstraint('equipo_id IS NOT NULL OR usuario_id IS NOT NULL', name='check_asignacion_target'),
        CheckConstraint('NOT (equipo_id IS NOT NULL AND usuario_id IS NOT NULL)', name='check_asignacion_exclusiva'),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    licencia_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("licencias_software.id", ondelete="CASCADE"), index=True)
    equipo_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("equipos.id", ondelete="CASCADE"), nullable=True, index=True)
    usuario_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=True, index=True)
    fecha_asignacion: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    instalado: Mapped[bool] = mapped_column(Boolean, default=True)
    notas: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    licencia: Mapped["LicenciaSoftware"] = relationship(
        "LicenciaSoftware",
        back_populates="asignaciones",
        lazy="joined"
    )
    equipo: Mapped[Optional["Equipo"]] = relationship(
        "Equipo",
        back_populates="licencias_asignadas_a_equipo",
        lazy="selectin"
    )
    usuario: Mapped[Optional["Usuario"]] = relationship(
        "Usuario",
        back_populates="licencias_asignadas",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        target = f"equipo_id={self.equipo_id}" if self.equipo_id else f"usuario_id={self.usuario_id}"
        return f"<AsignacionLicencia(id={self.id}, licencia_id={self.licencia_id}, target=[{target}])>"
