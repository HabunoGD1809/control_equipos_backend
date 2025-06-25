import logging
from typing import Optional, List
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import select

# Importar modelos
from app.models.login_log import LoginLog

logger = logging.getLogger(__name__) # Configurar logger

class LoginLogService:
    """
    Servicio para registrar y consultar los logs de intentos de acceso.
    La operación de log_attempt NO realiza commit.
    El commit debe ser manejado en la capa de la ruta (ej. en la ruta de login).
    """
    model = LoginLog

    def log_attempt(
        self,
        db: Session,
        *,
        username_attempt: Optional[str],
        success: Optional[bool], # Es mejor que sea bool, no Optional[bool], para claridad.
        ip_address: Optional[str],
        user_agent: Optional[str],
        fail_reason: Optional[str] = None,
        user_id: Optional[UUID] = None # ID del usuario si el intento fue sobre un usuario conocido o exitoso
    ) -> LoginLog:
        """
        Crea un nuevo registro de intento de login.
        NO realiza db.commit().
        """
        logger.debug(
            f"Registrando intento de login: UsuarioIntento='{username_attempt}', Exito={success}, "
            f"IP='{ip_address}', UserAgent='{user_agent}', UserID={user_id}, RazónFallo='{fail_reason}'"
        )
        db_obj = self.model(
            usuario_id=user_id,
            nombre_usuario_intento=username_attempt,
            exito=bool(success), # Asegurar que sea booleano
            ip_origen=ip_address,
            user_agent=user_agent,
            motivo_fallo=fail_reason
            # El campo 'intento' (timestamp) tiene un default en el modelo/BD (default=func.now())
        )
        db.add(db_obj)
        # db.commit() # ELIMINADO
        # db.refresh(db_obj) # ELIMINADO - Se hará en la ruta de login si se devuelve y necesita refresco
        
        logger.info(f"Intento de login para '{username_attempt}' (Exito: {success}) preparado para ser registrado.")
        return db_obj

    # --- Métodos de Lectura (ya usan select y no necesitan cambios de commit) ---
    def get(self, db: Session, id: UUID) -> Optional[LoginLog]:
        """Obtiene un log de intento de login por su ID."""
        logger.debug(f"Obteniendo log de login por ID: {id}")
        statement = select(self.model).where(self.model.id == id) # type: ignore[attr-defined]
        result = db.execute(statement)
        return result.scalar_one_or_none()

    def get_multi(
        self, db: Session, *, skip: int = 0, limit: int = 100
    ) -> List[LoginLog]:
        """Obtiene los logs de intentos de login más recientes."""
        logger.debug(f"Listando logs de login (skip: {skip}, limit: {limit}).")
        statement = select(self.model).order_by(self.model.intento.desc()).offset(skip).limit(limit) # type: ignore[attr-defined]
        result = db.execute(statement)
        return list(result.scalars().all())

    def get_multi_by_user(
        self, db: Session, *, usuario_id: UUID, skip: int = 0, limit: int = 100
    ) -> List[LoginLog]:
        """Obtiene logs de intentos de login para un usuario específico."""
        logger.debug(f"Listando logs de login para Usuario ID: {usuario_id} (skip: {skip}, limit: {limit}).")
        statement = select(self.model).where(self.model.usuario_id == usuario_id).order_by(self.model.intento.desc()).offset(skip).limit(limit) # type: ignore[attr-defined]
        result = db.execute(statement)
        return list(result.scalars().all())

    def get_multi_by_ip(
         self, db: Session, *, ip_origen: str, skip: int = 0, limit: int = 100
    ) -> List[LoginLog]:
         """Obtiene logs de intentos de login para una IP específica."""
         logger.debug(f"Listando logs de login para IP Origen: {ip_origen} (skip: {skip}, limit: {limit}).")
         statement = select(self.model).where(self.model.ip_origen == ip_origen).order_by(self.model.intento.desc()).offset(skip).limit(limit) # type: ignore[attr-defined]
         result = db.execute(statement)
         return list(result.scalars().all())

login_log_service = LoginLogService()
