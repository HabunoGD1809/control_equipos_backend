# -*- coding: utf-8 -*-
import uuid
from typing import TYPE_CHECKING, Optional, List
from datetime import datetime

from sqlalchemy import (
    Column, String, Text, DateTime, func, ForeignKey, BigInteger, Boolean,
    Index, text
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, TSVECTOR
from sqlalchemy.types import Text as TextType

from app.db.base import Base

if TYPE_CHECKING:
    from .equipo import Equipo
    from .mantenimiento import Mantenimiento
    from .licencia_software import LicenciaSoftware
    # -------------------------------------------------------------------------------
    from .tipo_documento import TipoDocumento
    from .usuario import Usuario


class Documentacion(Base):
    """
    Modelo ORM para la tabla 'documentacion'. (Actualizado con FKs y corrección TSVECTOR)
    """
    __tablename__ = "documentacion"
    __table_args__ = (
        Index("ix_documentacion_texto_busqueda", "texto_busqueda", postgresql_using="gin"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    equipo_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("equipos.id", ondelete="CASCADE"), nullable=True, index=True)
    mantenimiento_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("mantenimiento.id", ondelete="SET NULL"), nullable=True, index=True)
    licencia_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("licencias_software.id", ondelete="SET NULL"), nullable=True, index=True)
    tipo_documento_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tipos_documento.id", ondelete="RESTRICT"), index=True)
    titulo: Mapped[str] = mapped_column(String(255))
    descripcion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    enlace: Mapped[str] = mapped_column(Text) 
    nombre_archivo: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    mime_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    tamano_bytes: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    fecha_subida: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    subido_por: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True, index=True)
    estado: Mapped[str] = mapped_column(String(50), default='Pendiente', index=True) # Mantener string default
    verificado_por: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True, index=True)
    fecha_verificacion: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    notas_verificacion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    texto_busqueda = mapped_column(TSVECTOR, nullable=True, server_default=text("''"))

    # --- Relaciones ---
    equipo: Mapped[Optional["Equipo"]] = relationship(
        "Equipo", back_populates="documentos", lazy="selectin"
    )
    mantenimiento: Mapped[Optional["Mantenimiento"]] = relationship(
        "Mantenimiento", back_populates="documentos", lazy="selectin"
    )
    licencia: Mapped[Optional["LicenciaSoftware"]] = relationship(
        "LicenciaSoftware", back_populates="documentos", lazy="selectin"
    )
    tipo_documento: Mapped["TipoDocumento"] = relationship(
        "TipoDocumento", back_populates="documentos", lazy="joined"
    )
    subido_por_usuario: Mapped[Optional["Usuario"]] = relationship(
        "Usuario", foreign_keys=[subido_por], back_populates="documentos_subidos", lazy="selectin"
    )
    verificado_por_usuario: Mapped[Optional["Usuario"]] = relationship(
        "Usuario", foreign_keys=[verificado_por], back_populates="documentos_verificados", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Documentacion(id={self.id}, titulo='{self.titulo}')>"
