import uuid
from typing import TYPE_CHECKING, Optional
from datetime import datetime

from sqlalchemy import Column, String, Text, DateTime, func, ForeignKey
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base

if TYPE_CHECKING:
    from .equipo import Equipo
    from .usuario import Usuario

class ReservaEquipo(Base):
    """
    Modelo ORM para la tabla 'reservas_equipo', corregido y sincronizado.
    """
    __tablename__ = "reservas_equipo"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    equipo_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("equipos.id", ondelete="CASCADE"), index=True)
    usuario_solicitante_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="CASCADE"), index=True)
    
    fecha_hora_inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    fecha_hora_fin: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    
    proposito: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    estado: Mapped[str] = mapped_column(String(50), default='Confirmada', index=True)
    
    # --- Campos de Notas ---
    notas: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notas_administrador: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notas_devolucion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # --- Campos de Aprobación y Seguimiento ---
    aprobado_por_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True, index=True)
    fecha_aprobacion: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    check_in_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    check_out_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # --- Timestamps ---
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # --- Relaciones Corregidas ---
    equipo: Mapped["Equipo"] = relationship(back_populates="reservas", lazy="selectin")
    
    # El nombre de la propiedad AHORA COINCIDE con el schema (solicitante)
    solicitante: Mapped["Usuario"] = relationship(
        "Usuario",
        foreign_keys=[usuario_solicitante_id],
        back_populates="reservas_solicitadas",
        lazy="selectin"
    )
    
    # El nombre de la propiedad AHORA COINCIDE con el schema (aprobado_por)
    aprobado_por: Mapped[Optional["Usuario"]] = relationship(
        "Usuario",
        foreign_keys=[aprobado_por_id],
        back_populates="reservas_aprobadas",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<ReservaEquipo(id={self.id}, equipo_id={self.equipo_id}, inicio={self.fecha_hora_inicio})>"
