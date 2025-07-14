import sys
import os 
from os.path import abspath, dirname

root_dir = dirname(dirname(abspath(__file__)))
sys.path.append(root_dir)

from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.services.usuario import usuario_service
from app.services.rol import rol_service
from app.schemas.usuario import UsuarioCreate
from app.schemas.rol import RolCreate
from app.core.config import settings


def create_superuser():
    """
    Script síncrono para crear roles y un superusuario.
    """
    db: Session = SessionLocal()
    
    print("--- Iniciando script para crear superusuario ---")
    
    try:
        # 1. Verificar o crear el rol de 'admin'
        admin_role = rol_service.get_by_name(db, name="admin")
        if not admin_role:
            print("Rol 'admin' no encontrado, creándolo...")
            admin_role_schema = RolCreate(nombre="admin", descripcion="Rol de Administrador")
            admin_role = rol_service.create(db, obj_in=admin_role_schema)
            db.commit()
            db.refresh(admin_role)
            print(f"Rol 'admin' creado con ID: {admin_role.id}")
        else:
            print(f"Rol 'admin' ya existe con ID: {admin_role.id}")

        # --- CAMBIO #1: Leer email y pass desde variables de entorno ---
        admin_email = settings.SUPERUSER_EMAIL
        admin_password = settings.SUPERUSER_PASSWORD

        if not admin_password:
            print("!!! ERROR: La variable de entorno SUPERUSER_PASSWORD no está definida. Saliendo. !!!")
            return # Salimos del script si no hay contraseña

        # 2. Verificar si el superusuario ya existe
        superuser = usuario_service.get_by_email(db, email=admin_email)
        
        if not superuser:
            print(f"Creando superusuario con email: {admin_email}")
            
            superuser_in = UsuarioCreate(
                email=admin_email,
                password=admin_password,
                nombre_usuario="admin",
                rol_id=admin_role.id
            )
            usuario_service.create(db, obj_in=superuser_in)
            db.commit()
            print("¡Superusuario creado exitosamente!")
        else:
            print("El superusuario ya existe.")

    except Exception as e:
        print(f"Ocurrió un error: {e}")
        db.rollback()
    finally:
        print("--- Script finalizado ---")
        db.close()

if __name__ == "__main__":
    create_superuser()
