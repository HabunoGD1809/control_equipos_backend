import sys
import argparse
from os.path import abspath, dirname
from getpass import getpass

root_dir = dirname(dirname(abspath(__file__)))
sys.path.append(root_dir)

from app.db.session import SessionLocal
from app.services import usuario_service, rol_service
from app.schemas.usuario import UsuarioCreate
from app.core.permissions import (
    ADMIN_ROLE_NAME,
    SUPERVISOR_ROLE_NAME,
    AUDITOR_ROLE_NAME,
    TECNICO_ROLE_NAME,
    USUARIO_REGULAR_ROLE_NAME,
    TESTER_ROLE_NAME,
)

ROLES_PERMITIDOS = [
    ADMIN_ROLE_NAME,
    SUPERVISOR_ROLE_NAME,
    AUDITOR_ROLE_NAME,
    TECNICO_ROLE_NAME,
    USUARIO_REGULAR_ROLE_NAME,
    TESTER_ROLE_NAME,
]

# --- Funciones de Gestión (Crear/Eliminar) ---

def create_user(db, nombre: str, email: str, rol: str):
    """Crea un nuevo usuario en la base de datos."""
    print(f"Iniciando creación de usuario para el email: {email}")
    if usuario_service.get_by_email(db, email=email):
        print(f"❌ Error: Ya existe un usuario con el email '{email}'.")
        return
    rol_obj = rol_service.get_by_name(db, name=rol)
    if not rol_obj:
        print(f"❌ Error: El rol '{rol}' no fue encontrado en la base de datos.")
        return
    print(f"✔️ Rol '{rol}' encontrado con ID: {rol_obj.id}")
    password = getpass("Introduce la contraseña para el nuevo usuario: ")
    if not password or len(password) < 8:
        print("❌ Error: La contraseña no puede estar vacía y debe tener al menos 8 caracteres.")
        return
    try:
        user_in = UsuarioCreate(nombre_usuario=nombre, email=email, password=password, rol_id=rol_obj.id)
        usuario_service.create(db, obj_in=user_in)
        db.commit()
        print(f"✅ ¡Usuario '{nombre}' con rol '{rol}' creado exitosamente!")
    except Exception as e:
        db.rollback()
        print(f"❌ Error inesperado al crear el usuario: {e}")

def delete_user(db, email: str):
    """Elimina un usuario de la base de datos por su email."""
    print(f"Intentando eliminar al usuario con email: {email}")
    try:
        user = usuario_service.get_by_email(db, email=email)
        if user:
            db.delete(user)
            db.commit()
            print(f"✅ Usuario con email '{email}' eliminado exitosamente.")
        else:
            print(f"⚠️ No se encontró ningún usuario con el email '{email}'.")
    except Exception as e:
        print(f"❌ Error al eliminar usuario: {e}")
        db.rollback()

def list_users_with_roles(db):
    """Muestra una lista de todos los usuarios junto con sus roles asignados."""
    print("\n--- LISTA DE USUARIOS Y ROLES ---")
    all_users = usuario_service.get_multi(db, skip=0, limit=1000)
    if not all_users:
        print("-> No se encontraron usuarios en la base de datos.")
        return
    print(f"{'ROL':<18} | {'NOMBRE DE USUARIO':<25} | {'EMAIL'}")
    print("-" * 70)
    for user in all_users:
        rol_nombre = user.rol.nombre if user.rol else "SIN ROL"
        email = user.email if user.email else "No especificado"
        print(f"{rol_nombre:<18} | {user.nombre_usuario:<25} | {email}")
    print("-" * 70)
    print(f"Total: {len(all_users)} usuarios.")

def list_roles_only(db):
    """Muestra una lista de todos los roles disponibles en el sistema."""
    print("\n--- LISTA DE ROLES DEL SISTEMA ---")
    all_roles = rol_service.get_multi(db, skip=0, limit=100)
    if not all_roles:
        print("-> No se encontraron roles en la base de datos.")
        return
    print(f"{'ROL':<18} | {'DESCRIPCIÓN'}")
    print("-" * 70)
    for rol in all_roles:
        descripcion = rol.descripcion if rol.descripcion else "Sin descripción"
        print(f"{rol.nombre:<18} | {descripcion}")
    print("-" * 70)
    print(f"Total: {len(all_roles)} roles.")

# --- Interfaz de Línea de Comandos Principal ---

def main():
    parser = argparse.ArgumentParser(description="Herramienta CLI para gestionar el sistema.")
    subparsers = parser.add_subparsers(dest="command", help="Comandos disponibles", required=True)

    # Comando para crear un usuario
    parser_create = subparsers.add_parser("create", help="Crear un nuevo usuario.")
    parser_create.add_argument("--nombre", type=str, required=True, help="Nombre de usuario único.")
    parser_create.add_argument("--email", type=str, required=True, help="Email del usuario.")
    parser_create.add_argument("--rol", type=str, required=True, choices=ROLES_PERMITIDOS, help="Rol del usuario.")

    # Comando para eliminar un usuario
    parser_delete = subparsers.add_parser("delete", help="Eliminar un usuario existente.")
    parser_delete.add_argument("--email", type=str, required=True, help="Email del usuario a eliminar.")
    
    # Comando para listar usuarios y roles
    subparsers.add_parser("list-users", help="Mostrar una lista de todos los usuarios y sus roles.")
    
    # Comando para listar solo los roles
    subparsers.add_parser("list-roles", help="Mostrar una lista de todos los roles del sistema.")
    
    args = parser.parse_args()
    db = SessionLocal()
    try:
        if args.command == "create":
            create_user(db, nombre=args.nombre, email=args.email, rol=args.rol)
        elif args.command == "delete":
            delete_user(db, email=args.email)
        elif args.command == "list-users":
            list_users_with_roles(db)
        elif args.command == "list-roles":
            list_roles_only(db)
    finally:
        db.close()

if __name__ == "__main__":
    main()
