import sys
import getpass
import re
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

try:
    from colorama import Fore, Style, init  # type: ignore
    init(autoreset=True)
except ImportError:
    class Fore:
        GREEN = RED = YELLOW = BLUE = MAGENTA = ""
    class Style:
        BRIGHT = RESET_ALL = ""


# --- Funciones de validación ---

def is_valid_email(email: str) -> bool:
    """Valida si un string tiene formato de email."""
    regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(regex, email) is not None

def get_user_details() -> dict:
    """Solicita interactivamente los detalles del superusuario con validaciones."""
    default_username = getattr(settings, 'SUPERUSER_USERNAME', 'admin')
    default_email = getattr(settings, 'SUPERUSER_EMAIL', 'admin@example.com')
    default_password = getattr(settings, 'SUPERUSER_PASSWORD', '')

    print(Style.BRIGHT + "\nPor favor, introduce los datos para el superusuario.")
    print(f"{Fore.YELLOW}Si dejas un campo en blanco, se usará el valor por defecto.")

    # --- Nombre de Usuario ---
    while True:
        username_prompt = f"{Fore.GREEN}Nombre de usuario [{default_username}]: "
        username = input(username_prompt).strip() or default_username
        if " " in username:
            print(f"{Fore.RED}El nombre de usuario no puede contener espacios. Inténtalo de nuevo.")
            continue
        if not username:
            print(f"{Fore.RED}El nombre de usuario no puede estar vacío. Inténtalo de nuevo.")
            continue
        break

    # --- Email ---
    while True:
        email_prompt = f"{Fore.GREEN}Email [{default_email}]: "
        email = input(email_prompt).strip() or default_email
        if not is_valid_email(email):
            print(f"{Fore.RED}El formato del email no es válido. Inténtalo de nuevo.")
            continue
        break

    # --- Contraseña ---
    while True:
        password_prompt_1 = f"{Fore.GREEN}Contraseña (mín. 8 caracteres) [oculta]: "
        password = getpass.getpass(password_prompt_1)

        if not password and default_password:
            password = default_password
            print(f"{Fore.YELLOW}Usando la contraseña definida en el archivo .env.")
            break
        
        if len(password) < 9:
            print(f"{Fore.RED}La contraseña debe tener al menos 8 caracteres. Inténtalo de nuevo.")
            continue

        password_prompt_2 = f"{Fore.GREEN}Confirma la contraseña [oculta]: "
        password_confirm = getpass.getpass(password_prompt_2)
        if password != password_confirm:
            print(f"{Fore.RED}Las contraseñas no coinciden. Inténtalo de nuevo.")
            continue
        break

    return {"username": username, "email": email, "password": password}


def create_superuser():
    """Script interactivo y mejorado para crear el superusuario."""
    db: Session = SessionLocal()

    print(Style.BRIGHT + Fore.MAGENTA + "--- Script para Crear Superusuario ---")

    try:
        # 1. Verificar o crear el rol de 'admin'
        admin_role = rol_service.get_by_name(db, name=ADMIN_ROLE_NAME)
        if not admin_role:
            print(f"{Fore.YELLOW}Rol '{ADMIN_ROLE_NAME}' no encontrado, creándolo...")
            admin_role_schema = RolCreate(nombre=ADMIN_ROLE_NAME, descripcion="Rol de Administrador con todos los permisos")
            admin_role = rol_service.create(db, obj_in=admin_role_schema)
            db.commit()
            db.refresh(admin_role)
            print(f"{Fore.GREEN}Rol '{ADMIN_ROLE_NAME}' creado con ID: {admin_role.id}")
        else:
            print(f"Rol '{ADMIN_ROLE_NAME}' ya existe con ID: {admin_role.id}")

        # 2. Obtener detalles del usuario de forma interactiva
        user_details = get_user_details()

        # 3. Verificar si el superusuario ya existe
        superuser = usuario_service.get_by_email(db, email=user_details["email"])
        if not superuser:
            superuser = usuario_service.get_by_username(db, username=user_details["username"])

        if not superuser:
            print(f"\n{Style.BRIGHT}Creando superusuario '{user_details['username']}'...")
            
            superuser_in = UsuarioCreate(
                email=user_details["email"],
                password=user_details["password"],
                nombre_usuario=user_details["username"],
                rol_id=admin_role.id
            )
            usuario_service.create(db, obj_in=superuser_in)
            db.commit()
            print(f"\n{Style.BRIGHT}{Fore.GREEN}¡Superusuario creado exitosamente!")
        else:
            print(f"\n{Fore.YELLOW}El superusuario con email '{superuser.email}' o nombre de usuario '{superuser.nombre_usuario}' ya existe.")

    except Exception as e:
        print(f"\n{Fore.RED}{Style.BRIGHT}Ocurrió un error: {e}")
        db.rollback()
    finally:
        print(Style.BRIGHT + Fore.MAGENTA + "\n--- Script finalizado ---")
        db.close()

if __name__ == "__main__":
    try:
        create_superuser()
    except KeyboardInterrupt:
        print(f"\n\n{Fore.YELLOW}Operación cancelada por el usuario.{Style.RESET_ALL}")
        # Preguntar si desea salir
        try:
            confirm_exit = input("¿Estás seguro de que quieres salir? (s/N): ").lower()
            if confirm_exit == 's':
                print("Saliendo del script.")
                sys.exit(0)
            else:
                print("Continuando...")
                create_superuser()
        except KeyboardInterrupt:
             print("\nSaliendo del script.")
             sys.exit(0)

