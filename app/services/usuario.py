import logging
from typing import Any, Dict, Optional, Union
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import select
from fastapi import HTTPException, status

# Importar modelos y schemas
from app.models.usuario import Usuario
from app.schemas.usuario import UsuarioCreate, UsuarioUpdate

# Importar la clase base y otros servicios si son necesarios
from .base_service import BaseService
from .rol import rol_service

# Importar utilidades de contraseña y seguridad
from app.core.password import verify_password, get_password_hash

logger = logging.getLogger(__name__)

class UsuarioService(BaseService[Usuario, UsuarioCreate, UsuarioUpdate]):
    """
    Servicio para gestionar Usuarios. Incluye lógica para contraseñas y roles.
    """

    def get_by_username(self, db: Session, *, username: str) -> Optional[Usuario]:
        """Obtiene un usuario por su nombre de usuario."""
        statement = select(self.model).where(self.model.nombre_usuario == username)
        result = db.execute(statement)
        return result.scalar_one_or_none()

    def get_by_email(self, db: Session, *, email: str) -> Optional[Usuario]:
        """Obtiene un usuario por su correo electrónico."""
        statement = select(self.model).where(self.model.email == email)
        result = db.execute(statement)
        return result.scalar_one_or_none()

    def create(self, db: Session, *, obj_in: UsuarioCreate) -> Usuario:
        """
        Crea un nuevo usuario.
        NO realiza db.commit().
        """
        logger.debug(f"Intentando crear usuario: {obj_in.nombre_usuario}")
        existing_user = self.get_by_username(db, username=obj_in.nombre_usuario)
        if existing_user:
            logger.warning(f"Intento de crear usuario con nombre de usuario duplicado: {obj_in.nombre_usuario}")
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ya existe un usuario con ese nombre de usuario.")
        
        if obj_in.email:
            existing_email = self.get_by_email(db, email=obj_in.email)
            if existing_email:
                logger.warning(f"Intento de crear usuario con email duplicado: {obj_in.email}")
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ya existe un usuario con ese correo electrónico.")

        if obj_in.rol_id:
            rol = rol_service.get(db, id=obj_in.rol_id)
            if not rol:
                logger.error(f"Rol con ID {obj_in.rol_id} no encontrado al crear usuario.")
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"El Rol con ID {obj_in.rol_id} no fue encontrado.")
        else:
            logger.error("Intento de crear usuario sin rol_id.")
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="El campo rol_id es obligatorio.")

        create_data = obj_in.model_dump()
        plain_password = create_data.pop("password")
        create_data["hashed_password"] = get_password_hash(plain_password)

        db_obj = self.model(**create_data)

        db.add(db_obj)
        logger.info(f"Usuario '{db_obj.nombre_usuario}' preparado para ser creado.")
        return db_obj

    def update(
        self,
        db: Session,
        *,
        db_obj: Usuario,
        obj_in: Union[UsuarioUpdate, Dict[str, Any]]
    ) -> Usuario:
        """
        Actualiza un usuario existente.
        NO realiza db.commit().
        """
        update_data = obj_in if isinstance(obj_in, dict) else obj_in.model_dump(exclude_unset=True)
        user_id = db_obj.id

        logger.debug(f"Intentando actualizar usuario ID {user_id} con datos: {update_data}")

        if "password" in update_data and update_data["password"]:
            plain_password = update_data.pop("password")
            update_data["hashed_password"] = get_password_hash(plain_password)
            logger.info(f"Contraseña actualizada para usuario ID {user_id}.")
        elif "password" in update_data:
            update_data.pop("password")

        if "rol_id" in update_data and update_data["rol_id"] is not None:
            if update_data["rol_id"] != db_obj.rol_id:
                rol = rol_service.get(db, id=update_data["rol_id"])
                if not rol:
                    logger.error(f"Rol con ID {update_data['rol_id']} no encontrado al actualizar usuario {user_id}.")
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"El Rol con ID {update_data['rol_id']} no fue encontrado.")
                logger.info(f"Rol actualizado para usuario ID {user_id} a rol ID {update_data['rol_id']}.")
        elif "rol_id" in update_data and update_data["rol_id"] is None:
            logger.warning(f"Intento de asignar rol_id nulo a usuario ID {user_id}, lo cual no está permitido.")
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="No se puede asignar un rol nulo al usuario.")

        if "nombre_usuario" in update_data and update_data["nombre_usuario"] != db_obj.nombre_usuario:
            logger.debug(f"Validando nuevo nombre de usuario '{update_data['nombre_usuario']}' para usuario ID {user_id}.")
            existing_user = self.get_by_username(db, username=update_data["nombre_usuario"])
            if existing_user and existing_user.id != user_id:
                logger.warning(f"Conflicto de nombre de usuario al actualizar ID {user_id} a '{update_data['nombre_usuario']}'. Ya existe.")
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Nombre de usuario ya registrado por otro usuario.")
        
        if "email" in update_data and update_data["email"] is not None:
            if update_data["email"] != db_obj.email:
                logger.debug(f"Validando nuevo email '{update_data['email']}' para usuario ID {user_id}.")
                existing_email = self.get_by_email(db, email=update_data["email"])
                if existing_email and existing_email.id != user_id:
                    logger.warning(f"Conflicto de email al actualizar ID {user_id} a '{update_data['email']}'. Ya existe.")
                    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Correo electrónico ya registrado por otro usuario.")
        elif "email" in update_data and update_data["email"] is None:
            pass

        updated_db_obj = super().update(db, db_obj=db_obj, obj_in=update_data)
        logger.info(f"Usuario ID {user_id} ('{updated_db_obj.nombre_usuario}') preparado para ser actualizado.")
        return updated_db_obj

    def authenticate(
        self, db: Session, *, username: str, password: str
    ) -> Optional[Usuario]:
        """
        Autentica a un usuario. Verifica nombre de usuario y contraseña.
        """
        user = self.get_by_username(db, username=username)
        if not user:
            logger.warning(f"Intento de login fallido: Usuario '{username}' no encontrado.")
            return None
        if user.bloqueado:
            logger.warning(f"Intento de login fallido: Usuario '{username}' está bloqueado.")
            return None
        if not verify_password(password, user.hashed_password):
            logger.warning(f"Intento de login fallido: Contraseña incorrecta para usuario '{username}'.")
            return None
        
        logger.info(f"Usuario '{username}' autenticado exitosamente.")
        return user

    def is_active(self, user: Usuario) -> bool:
        """Verifica si un usuario está activo (no bloqueado)."""
        return not user.bloqueado

    def needs_password_change(self, user: Usuario) -> bool:
        """Verifica si el usuario necesita cambiar su contraseña."""
        return user.requiere_cambio_contrasena
    
    def remove(self, db: Session, *, id: Union[UUID, int]) -> Usuario:
        """
        Elimina un usuario. 
        NO realiza db.commit().
        """
        logger.debug(f"Intentando eliminar usuario ID: {id}")
        deleted_obj = super().remove(db, id=id)
        logger.warning(f"Usuario '{deleted_obj.nombre_usuario}' (ID: {id}) preparado para ser eliminado.")
        return deleted_obj

usuario_service = UsuarioService(Usuario)
