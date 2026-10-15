"""Initialize catalogs and a usable administrator. Never prints passwords."""
import argparse
import getpass
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.password import get_password_hash, verify_password
from app.db.session import SessionLocal
from app.models import Usuario
from app.schemas.usuario import UsuarioCreate
from app.db.seed import seed_system_catalogs


def bootstrap(db: Session, username: str, email: str, password: str, *, reset_password=False):
    role = seed_system_catalogs(db)
    from pydantic import ValidationError
    try:
        validated=UsuarioCreate(nombre_usuario=username,email=email,password=password,rol_id=role.id)
    except ValidationError:
        raise ValueError('El usuario, correo o contraseña no cumple las reglas de validación.') from None
    user=db.scalar(select(Usuario).where(Usuario.nombre_usuario==username))
    if not user:
        user=Usuario(nombre_usuario=validated.nombre_usuario,email=str(validated.email),hashed_password=get_password_hash(password),rol_id=role.id,bloqueado=False,intentos_fallidos=0,requiere_cambio_contrasena=True)
        db.add(user)
    elif reset_password:
        from app.services.usuario import usuario_service
        user = usuario_service._lock(db, user)
        usuario_service.revoke_sessions(db, user)
        user.hashed_password=get_password_hash(password)
        user.rol_id=role.id
        user.bloqueado=False
        user.intentos_fallidos=0
        user.requiere_cambio_contrasena=True
    db.commit()
    db.refresh(user)
    if (reset_password or verify_password(password,user.hashed_password)) and not user.bloqueado:
        print(f"Administrador listo: {username}. Contraseña verificada. Se solicitará cambiarla al ingresar.")
    else:
        print(f"El administrador {username} ya existe. Su contraseña se conserva; use --reset-password para cambiarla.")
    return user


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-env",action="store_true",help="Usar SUPERUSER_USERNAME, SUPERUSER_EMAIL y SUPERUSER_PASSWORD de .env")
    parser.add_argument("--reset-password",action="store_true",help="Restablecer explícitamente la contraseña de un administrador existente")
    args=parser.parse_args()
    if args.from_env:
        username,email,password=settings.SUPERUSER_USERNAME,str(settings.SUPERUSER_EMAIL),settings.SUPERUSER_PASSWORD
    else:
        username=input(f"Usuario [{settings.SUPERUSER_USERNAME}]: ").strip() or settings.SUPERUSER_USERNAME
        email=input(f"Correo [{settings.SUPERUSER_EMAIL}]: ").strip() or str(settings.SUPERUSER_EMAIL)
        password=getpass.getpass("Contraseña (8 caracteres como mínimo): ")
        if password!=getpass.getpass("Confirme la contraseña: "):
            raise ValueError("Las contraseñas no coinciden.")
    with SessionLocal() as db:
        bootstrap(db,username,email,password,reset_password=args.reset_password)


if __name__=="__main__":
    main()
