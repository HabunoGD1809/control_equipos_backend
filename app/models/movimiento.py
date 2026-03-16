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
    from .ubicacion import Ubicacion

class Movimiento(Base):
    """
    Modelo ORM para la tabla 'movimientos'. 
    """
    __tablename__ = "movimientos"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    equipo_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("equipos.id", ondelete="CASCADE"), index=True)
    usuario_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True, index=True)
    tipo_movimiento: Mapped[str] = mapped_column(String(50), index=True)
    fecha_hora: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    fecha_prevista_retorno: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    fecha_retorno: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    ubicacion_origen_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("ubicaciones.id", ondelete="SET NULL"), nullable=True, index=True)
    ubicacion_destino_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("ubicaciones.id", ondelete="SET NULL"), nullable=True, index=True)
    
    proposito: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    autorizado_por: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True, index=True)
    recibido_por: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    observaciones: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    estado: Mapped[str] = mapped_column(String(50), default='Completado', index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())    
    ip_origen: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    equipo: Mapped["Equipo"] = relationship(
        "Equipo",
        back_populates="movimientos",
        lazy="joined"
    )
    usuario_registrador: Mapped[Optional["Usuario"]] = relationship(
        "Usuario",
        foreign_keys=[usuario_id],
        back_populates="movimientos_registrados",
        lazy="selectin"
    )
    usuario_autorizador: Mapped[Optional["Usuario"]] = relationship(
        "Usuario",
        foreign_keys=[autorizado_por],
        back_populates="movimientos_autorizados",
        lazy="selectin"
    )
    
    # Relaciones con Ubicaciones (para JOINs automáticos)
    ubicacion_origen: Mapped[Optional["Ubicacion"]] = relationship(
        "Ubicacion",
        foreign_keys=[ubicacion_origen_id],
        lazy="selectin"
    )
    ubicacion_destino: Mapped[Optional["Ubicacion"]] = relationship(
        "Ubicacion",
        foreign_keys=[ubicacion_destino_id],
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Movimiento(id={self.id}, equipo_id={self.equipo_id}, tipo='{self.tipo_movimiento}', estado='{self.estado}')>"
