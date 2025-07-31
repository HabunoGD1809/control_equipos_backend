import logging
from typing import Any, Dict, Optional, Union
from uuid import UUID, uuid4
from datetime import datetime, timezone, timedelta

from sqlalchemy.orm import Session
from sqlalchemy import select
from fastapi import HTTPException, status

# Importar modelos y schemas
# from app.core.permissions import ADMIN_ROLE_NAME
from app.models.usuario import Usuario
from app.schemas.usuario import UsuarioCreate, UsuarioUpdate
from app.schemas.password import PasswordChange

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
        [MODIFICADO] Ahora maneja los intentos fallidos.
        """
        user = self.get_by_username(db, username=username)
        if not user:
            logger.warning(f"Intento de login fallido: Usuario '{username}' no encontrado.")
            return None
        
        # Aunque el usuario ya esté bloqueado, lo devolvemos para que el endpoint
        # maneje el mensaje de error específico.
        if user.bloqueado:
            logger.warning(f"Intento de login para usuario '{username}' que ya está bloqueado.")
            # No retornamos None aquí, para que el endpoint pueda diferenciar
            # entre 'bloqueado' y 'credenciales incorrectas'.
            # El método is_active se encargará de esto.
            return user

        if not verify_password(password, user.hashed_password):
            logger.warning(f"Intento de login fallido: Contraseña incorrecta para usuario '{username}'.")
            # --- Lógica para intento fallido ---
            user.intentos_fallidos = (user.intentos_fallidos or 0) + 1
            if user.intentos_fallidos >= 5: # Límite de intentos
                user.bloqueado = True
                logger.warning(f"Usuario '{username}' bloqueado por exceder 5 intentos fallidos.")
            
            try:
                db.add(user)
                db.commit() # Guardamos el intento fallido
            except Exception as e:
                logger.error(f"Error al actualizar intentos fallidos para {username}: {e}")
                db.rollback()
            return None # La autenticación falló
        
        # Si la contraseña es correcta pero estaba bloqueado, no debería pasar, pero como salvaguarda
        if user.bloqueado:
             return user # Dejar que el endpoint lo maneje con is_active

        logger.info(f"Usuario '{username}' autenticado preliminarmente (contraseña correcta).")
        return user

    def is_active(self, user: Usuario) -> bool:
        """Verifica si un usuario está activo (no bloqueado)."""
        return not user.bloqueado
    
    # def is_admin(self, user: Usuario) -> bool:
    #     """
    #     Verifica si un usuario tiene el rol de 'admin'.
    #     Es una comprobación de conveniencia.
    #     """
        
    #     if user and user.rol:
    #         return user.rol.nombre == ADMIN_ROLE_NAME
    #     return False
    
    def needs_password_change(self, user: Usuario) -> bool:
        """Verifica si el usuario necesita cambiar su contraseña."""
        return user.requiere_cambio_contrasena
    
    def handle_successful_login(self, db: Session, *, user: Usuario) -> None:
        """
        Actualiza los campos del usuario tras un login exitoso.
        Resetea intentos fallidos y actualiza la fecha de último login.
        NO realiza db.commit().
        """
        logger.debug(f"Preparando actualización de campos de login para usuario: {user.nombre_usuario}")
        user.ultimo_login = datetime.now(timezone.utc)
        user.intentos_fallidos = 0
        db.add(user) # Añade el objeto a la sesión para marcarlo como 'dirty'
        logger.info(f"Campos de login exitoso preparados para {user.nombre_usuario}.")


    def remove(self, db: Session, *, id: Union[UUID, int]) -> Usuario:
        """
        Elimina un usuario. 
        NO realiza db.commit().
        """
        logger.debug(f"Intentando eliminar usuario ID: {id}")
        db_obj = self.get(db, id=id)
        if not db_obj:
             raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
        
        nombre_usuario_eliminado = db_obj.nombre_usuario
        
        db.delete(db_obj)
        logger.warning(f"Usuario '{nombre_usuario_eliminado}' (ID: {id}) preparado para ser eliminado.")
        # La convención es no devolver el objeto, ya que se eliminará.
        # Pero si se necesita para logs, se puede devolver.
        return db_obj

    def change_password(
        self, db: Session, *, user: Usuario, password_data: PasswordChange
    ) -> Usuario:
        """
        Permite a un usuario autenticado cambiar su propia contraseña.
        Verifica la contraseña actual antes de establecer una nueva.
        NO realiza db.commit().
        """
        logger.info(f"Iniciando cambio de contraseña para el usuario: {user.nombre_usuario}")

        # 1. Verificar la contraseña actual
        if not verify_password(password_data.current_password, user.hashed_password):
            logger.warning(f"Intento de cambio de contraseña fallido para '{user.nombre_usuario}': contraseña actual incorrecta.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La contraseña actual es incorrecta.",
            )

        # 2. Hashear y actualizar la nueva contraseña
        user.hashed_password = get_password_hash(password_data.new_password)
        
        # 3. Marcar que ya no se requiere cambio de contraseña
        user.requiere_cambio_contrasena = False

        db.add(user)
        logger.info(f"Contraseña actualizada exitosamente para el usuario '{user.nombre_usuario}'.")
        return user

    # --- Método para iniciar el reseteo de contraseña ---
    def initiate_password_reset(self, db: Session, *, username: str) -> Usuario:
        """
        Genera y guarda un token de reseteo temporal para un usuario.
        NO realiza db.commit().
        """
        user = self.get_by_username(db, username=username)
        if not user:
            logger.error(f"Intento de reseteo de contraseña para usuario no existente: {username}")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado.")
        
        user.token_temporal = uuid4()
        user.token_expiracion = datetime.now(timezone.utc) + timedelta(minutes=15) # Token válido por 15 minutos
        
        db.add(user)
        logger.info(f"Token de reseteo de contraseña generado para el usuario '{username}'.")
        return user

    # --- Método para confirmar el reseteo de contraseña ---
    def confirm_password_reset(
        self, db: Session, *, username: str, token: UUID, new_password: str
    ) -> Usuario:
        """
        Verifica el token y actualiza la contraseña del usuario.
        NO realiza db.commit().
        """
        user = self.get_by_username(db, username=username)

        # Validaciones de seguridad
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado.")
        
        if not user.token_temporal or user.token_temporal != token:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token de reseteo inválido.")
            
        if not user.token_expiracion or user.token_expiracion < datetime.now(timezone.utc):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El token de reseteo ha expirado.")

        # Si todo es correcto, actualizamos la contraseña y limpiamos los tokens
        user.hashed_password = get_password_hash(new_password)
        user.token_temporal = None
        user.token_expiracion = None
        user.requiere_cambio_contrasena = False # El usuario acaba de establecer su contraseña
        user.bloqueado = False # Desbloquear al usuario si estaba bloqueado
        user.intentos_fallidos = 0

        db.add(user)
        logger.info(f"Contraseña reseteada exitosamente para el usuario '{username}'.")
        return user

usuario_service = UsuarioService(Usuario)
