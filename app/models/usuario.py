import datetime
import uuid
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    DateTime, ForeignKey, Integer, Boolean, String
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base

if TYPE_CHECKING:
    from .rol import Rol
    from .movimiento import Movimiento
    from .notificacion import Notificacion
    from .login_log import LoginLog
    from .documentacion import Documentacion
    from .asignacion_licencia import AsignacionLicencia
    from .reserva_equipo import ReservaEquipo
    from .inventario_movimiento import InventarioMovimiento


class Usuario(Base):
    """
    Modelo ORM para la tabla 'usuarios'.
    """
    __tablename__ = "usuarios"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre_usuario: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column("contrasena", String)
    rol_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("roles.id"), index=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True, index=True)
    token_temporal: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    token_expiracion: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    intentos_fallidos: Mapped[int] = mapped_column(Integer, default=0)
    bloqueado: Mapped[bool] = mapped_column(Boolean, default=False)
    ultimo_login: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    requiere_cambio_contrasena: Mapped[bool] = mapped_column(Boolean, default=True)

    rol: Mapped["Rol"] = relationship("Rol", back_populates="usuarios", lazy="selectin")

    movimientos_registrados: Mapped[List["Movimiento"]] = relationship(
        "Movimiento",
        foreign_keys="Movimiento.usuario_id",
        back_populates="usuario_registrador",
        lazy="selectin"
    )
    movimientos_autorizados: Mapped[List["Movimiento"]] = relationship(
        "Movimiento",
        foreign_keys="Movimiento.autorizado_por",
        back_populates="usuario_autorizador",
        lazy="selectin"
    )
    notificaciones: Mapped[List["Notificacion"]] = relationship(
        "Notificacion",
        back_populates="usuario",
        lazy="selectin",
        cascade="all, delete-orphan"
    )
    logs_acceso: Mapped[List["LoginLog"]] = relationship(
        "LoginLog",
        back_populates="usuario",
        lazy="selectin"
    )
    documentos_subidos: Mapped[List["Documentacion"]] = relationship(
        "Documentacion",
        foreign_keys="Documentacion.subido_por",
        back_populates="subido_por_usuario",
        lazy="selectin"
    )
    documentos_verificados: Mapped[List["Documentacion"]] = relationship(
        "Documentacion",
        foreign_keys="Documentacion.verificado_por",
        back_populates="verificado_por_usuario",
        lazy="selectin"
    )
    licencias_asignadas: Mapped[List["AsignacionLicencia"]] = relationship(
        "AsignacionLicencia",
        foreign_keys="AsignacionLicencia.usuario_id",
        back_populates="usuario",
        lazy="selectin",
        cascade="all, delete-orphan"
    )
    reservas_solicitadas: Mapped[List["ReservaEquipo"]] = relationship(
        "ReservaEquipo",
        foreign_keys="ReservaEquipo.usuario_solicitante_id",
        back_populates="solicitante", 
        lazy="selectin",
        cascade="all, delete-orphan"
    )
    reservas_aprobadas: Mapped[List["ReservaEquipo"]] = relationship(
        "ReservaEquipo",
        foreign_keys="ReservaEquipo.aprobado_por_id",
        back_populates="aprobado_por",
        lazy="selectin"
    )
    movimientos_inventario_registrados: Mapped[List["InventarioMovimiento"]] = relationship(
        "InventarioMovimiento",
        foreign_keys="InventarioMovimiento.usuario_id",
        back_populates="usuario_registrador",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Usuario(id={self.id}, nombre_usuario='{self.nombre_usuario}')>"
