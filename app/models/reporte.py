import uuid
from typing import Optional, Dict, Any
from datetime import datetime

from sqlalchemy import String, Text, DateTime, Integer, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.db.base import Base

class Reporte(Base):
    """
    Modelo ORM para la tabla 'reportes', gestiona el estado y metadata de la exportación de datos.
    """
    __tablename__ = "reportes"
    __table_args__ = {"schema": "control_equipos"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    
    usuario_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("control_equipos.usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    
    tipo_reporte: Mapped[str] = mapped_column(String, nullable=False, index=True)
    formato: Mapped[str] = mapped_column(String, nullable=False)
    
    # JSONB para guardar los filtros exactos que el usuario usó
    parametros: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    
    estado: Mapped[str] = mapped_column(String, nullable=False, default="pendiente", index=True)
    
    archivo_path: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    archivo_size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error_msg: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    fecha_solicitud: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    fecha_completado: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relación recomendada para consultas
    usuario = relationship("Usuario", back_populates="reportes_solicitados", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Reporte(id={self.id}, tipo='{self.tipo_reporte}', estado='{self.estado}')>"
