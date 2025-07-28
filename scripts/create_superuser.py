import sys
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
from app.core.permissions import ADMIN_ROLE_NAME

def create_superuser():
    """
    Script síncrono para crear el rol 'admin' y un superusuario a partir de variables de entorno.
    """
    db: Session = SessionLocal()
    
    print("--- Iniciando script para crear superusuario ---")
    
    try:
        # 1. Verificar o crear el rol de 'admin'
        admin_role = rol_service.get_by_name(db, name=ADMIN_ROLE_NAME)
        if not admin_role:
            print(f"Rol '{ADMIN_ROLE_NAME}' no encontrado, creándolo...")
            admin_role_schema = RolCreate(nombre=ADMIN_ROLE_NAME, descripcion="Rol de Administrador con todos los permisos")
            admin_role = rol_service.create(db, obj_in=admin_role_schema)
            db.commit()
            db.refresh(admin_role)
            print(f"Rol '{ADMIN_ROLE_NAME}' creado con ID: {admin_role.id}")
        else:
            print(f"Rol '{ADMIN_ROLE_NAME}' ya existe con ID: {admin_role.id}")

        # 2. Leer credenciales desde variables de entorno
        admin_email = settings.SUPERUSER_EMAIL
        admin_password = settings.SUPERUSER_PASSWORD

        if not all([admin_email, admin_password]):
            print("!!! ERROR: Define SUPERUSER_EMAIL y SUPERUSER_PASSWORD en tu archivo .env. Saliendo. !!!")
            return

        # 3. Verificar si el superusuario ya existe
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
            print(f"El superusuario con email '{admin_email}' ya existe.")

    except Exception as e:
        print(f"Ocurrió un error: {e}")
        db.rollback()
    finally:
        print("--- Script finalizado ---")
        db.close()

if __name__ == "__main__":
    create_superuser()
