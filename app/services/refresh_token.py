import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.config import settings
from app.core.password import hash_token, verify_token_hash
from app.models.refresh_token import RefreshToken
from app.schemas.token import RefreshTokenCreate, RefreshTokenUpdate
from .base_service import BaseService

logger = logging.getLogger(__name__)


class RefreshTokenService(BaseService[RefreshToken, RefreshTokenCreate, RefreshTokenUpdate]):

    def create_token(self, db: Session, *, obj_in: RefreshTokenCreate, user_agent: str, ip_address: str) -> RefreshToken:
        """
        Crea y almacena un nuevo refresh token en la base de datos.
        Usa SHA-256 para hashear el token (bcrypt tiene limite de 72 bytes).
        """
        token_hash = hash_token(obj_in.token)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES)

        db_obj = self.model(
            usuario_id=obj_in.usuario_id,
            token_hash=token_hash,
            expires_at=expires_at,
            user_agent=user_agent,
            ip_address=ip_address
        )
        db.add(db_obj)
        return db_obj

    def get_by_token_hash(self, db: Session, *, token_hash: str) -> Optional[RefreshToken]:
        """
        Busca un refresh token por su hash SHA-256.
        """
        statement = select(self.model).where(self.model.token_hash == token_hash)
        return db.execute(statement).scalar_one_or_none()

    def get_by_plain_token(self, db: Session, *, token: str) -> Optional[RefreshToken]:
        """
        Busca un refresh token a partir del token en texto plano.
        Convierte a hash internamente antes de buscar.
        """
        return self.get_by_token_hash(db, token_hash=hash_token(token))

    def revoke_token(self, db: Session, *, token_obj: RefreshToken, plain_token: str) -> RefreshToken:
        """
        Marca un token como revocado (invalidado).
        Verifica que el token plano corresponda al hash almacenado antes de revocar.
        """
        if not verify_token_hash(plain_token, token_obj.token_hash):
            raise ValueError("El token proporcionado no coincide con el hash almacenado.")
        token_obj.revoked_at = datetime.now(timezone.utc)
        db.add(token_obj)
        return token_obj


refresh_token_service = RefreshTokenService(RefreshToken)
