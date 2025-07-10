import pytest
import pytest_asyncio
from typing import AsyncGenerator, Generator, Any, List, Dict, Set
from uuid import uuid4
from unittest import mock
from datetime import datetime, timedelta, timezone, date
from decimal import Decimal
import json
import logging

import httpx
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from sqlalchemy import create_engine, text, select, delete
from sqlalchemy.orm import sessionmaker, Session, selectinload, joinedload

from app.models import ( # noqa
    Usuario, Rol, Permiso, EstadoEquipo, Proveedor, TipoDocumento,
    TipoMantenimiento, Equipo, ReservaEquipo, Notificacion,
    TipoItemInventario, InventarioStock, InventarioMovimiento,
    SoftwareCatalogo, LicenciaSoftware, AsignacionLicencia,
    Documentacion, EquipoComponente, RolPermiso
)

from app.main import app as fastapi_app

from app.core.config import settings
from app.api.deps import get_db # Usado para override

from app.core.password import get_password_hash, verify_password

from app.schemas.enums import (
    UnidadMedidaEnum,
    EstadoReservaEnum,
    EstadoDocumentoEnum,
    TipoNotificacionEnum,
    MetricaLicenciamientoEnum,
    TipoLicenciaSoftwareEnum,
)

# Configuración básica de logging para los tests
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] [%(name)s] [%(funcName)s] %(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG) # DEBUG

TEST_SQLALCHEMY_DATABASE_URL = str(settings.DATABASE_URI)
logger.info(f"Usando URL de BD para tests: {TEST_SQLALCHEMY_DATABASE_URL}")
engine = create_engine(TEST_SQLALCHEMY_DATABASE_URL, echo=False, pool_pre_ping=True)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="session")
def app() -> FastAPI:
    """
    Fixture que proporciona la instancia de la aplicación FastAPI para los tests.
    """
    return fastapi_app

@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    logger.info("== Iniciando configuración de DB para la sesión de tests ==")
    yield
    logger.info("== Finalizando configuración de DB para la sesión de tests ==")

@pytest.fixture(scope="function")
def db() -> Generator[Session, None, None]:
    """Fixture para obtener una sesión de BD por cada test."""
    connection = engine.connect()
    transaction = connection.begin()
    db_session = TestingSessionLocal(bind=connection)
    session_identifier = getattr(db_session, 'hash_key', id(db_session))
    logger.debug(f"DB Session {session_identifier} iniciada para test.")
    try:
        yield db_session
    finally:
        logger.debug(f"DB Session {session_identifier}: Rollback y cierre.")
        db_session.close()
        if transaction.is_active:
            transaction.rollback()
        connection.close()
        logger.debug(f"DB Session {session_identifier}: Cerrada y rollback completado.")

@pytest_asyncio.fixture(scope="function")
async def client(app: FastAPI, db: Session) -> AsyncGenerator[AsyncClient, None]:
    """Fixture para obtener un cliente HTTP asíncrono para interactuar con la app."""
    def override_get_db_for_test():
        nonlocal db
        session_identifier = getattr(db, 'hash_key', id(db))
        logger.debug(f"Override get_db: Proporcionando sesión {session_identifier}")
        try:
            yield db
        finally:
            logger.debug(f"Override get_db: Finalizando uso de sesión {session_identifier}")
            pass

    original_get_db = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db_for_test
    logger.debug(f"AsyncClient: Dependencia get_db sobreescrita con {override_get_db_for_test}")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as test_client:
        logger.debug(f"AsyncClient creado para test contra app: {app}")
        yield test_client

    if original_get_db:
        app.dependency_overrides[get_db] = original_get_db
        logger.debug("AsyncClient: Dependencia get_db restaurada.")
    else:
        # --- CORRECCIÓN FINAL ---
        # Usamos .pop() en lugar de 'del'. Esto elimina la clave si existe,
        # y no hace nada (sin dar error) si ya fue eliminada por otro lado.
        app.dependency_overrides.pop(get_db, None)
        logger.debug("AsyncClient: Dependencia get_db eliminada del override (de forma segura).")
    logger.debug("AsyncClient fixtures limpiados.")


async def get_auth_token(client: AsyncClient, username: str, password: str) -> str | None:
    """Función helper para obtener un token de autenticación."""
    login_data = {"username": username, "password": password}
    url = f"{settings.API_V1_STR}/auth/login/access-token"
    logger.info(f"Solicitando token para usuario '{username}' en {url}")
    try:
        with mock.patch("app.api.routes.auth.log_login_attempt_task"):
            response = await client.post(url, data=login_data)
        logger.debug(f"Respuesta de login para '{username}': Status {response.status_code}, Body: {response.text[:100]}...") # Log limitado
        response.raise_for_status()
        token_data = response.json()
        access_token = token_data.get("access_token")
        if access_token:
            logger.info(f"Token obtenido exitosamente para '{username}'.")
            return access_token
        else:
            logger.error(f"No se encontró 'access_token' en la respuesta para '{username}'. Respuesta: {token_data}")
            return None
    except httpx.HTTPStatusError as e:
        status_code = e.response.status_code
        try:
            error_detail = e.response.json()
        except json.JSONDecodeError:
            error_detail = e.response.text
        logger.error(f"FALLO al obtener token para '{username}' en get_auth_token: Status={status_code}, Error={type(e).__name__}. Detail: {error_detail}", exc_info=False)
        return None
    except Exception as e:
        logger.error(f"FALLO INESPERADO al obtener token para '{username}': Error={type(e).__name__}. Detail: {e}", exc_info=True)
        return None

# Contraseñas de prueba
TEST_USER_REGULAR_PASSWORD = "UsuarioPass123!"
TEST_ADMIN_PASSWORD = "AdminPass123!"
TEST_SUPERVISOR_PASSWORD = "SuperPass123!"
TEST_TECNICO_PASSWORD = "TecnicoPass123!"
TEST_AUDITOR_PASSWORD = "AuditorPass123!"
TEST_TESTER_PASSWORD = "TesterPass123!"


@pytest.fixture(scope="function")
def test_permisos_definidos(db: Session) -> Dict[str, Permiso]:
    logger.debug("Inicio fixture: test_permisos_definidos")
    perm_names = [
        "administrar_catalogos", "administrar_inventario_stock", "administrar_inventario_tipos", "administrar_licencias", "administrar_roles",
        "administrar_sistema", "administrar_software_catalogo", "administrar_usuarios", "aprobar_reservas", "asignar_licencias",
        "autorizar_movimientos", "cancelar_movimientos", "configurar_sistema", "crear_equipos", "editar_documentos",
        "editar_equipos", "editar_mantenimientos", "editar_movimientos", "eliminar_documentos", "eliminar_equipos",
        "eliminar_mantenimientos", "generar_reportes", "gestionar_componentes", "programar_mantenimientos", "registrar_movimientos",
        "reservar_equipos", "subir_documentos", "ver_auditoria", "ver_dashboard", "ver_documentos",
        "ver_equipos", "ver_inventario", "ver_licencias", "ver_mantenimientos", "ver_movimientos",
        "ver_proveedores", "ver_reservas", "verificar_documentos"
    ]
    permisos_dict = {}
    try:
        existing_perms_query = db.query(Permiso).filter(Permiso.nombre.in_(perm_names))
        existing_perms = {p.nombre: p for p in existing_perms_query.all()}
        logger.debug(f"Permisos existentes encontrados en BD: {len(existing_perms)}/{len(perm_names)}")
    except Exception as e:
        logger.critical(f"Error al consultar permisos existentes en la BD: {e}", exc_info=True)
        pytest.fail(f"Error crítico consultando permisos en la BD: {e}")

    newly_created_perms: List[Permiso] = []
    for name in perm_names:
        if name not in existing_perms:
            logger.warning(f"Permiso '{name}' NO encontrado en BD para tests, creando...")
            perm = Permiso(nombre=name, descripcion=f"Permiso Test: {name}") # type: ignore
            db.add(perm)
            permisos_dict[name] = perm
            newly_created_perms.append(perm)
        else:
            permisos_dict[name] = existing_perms[name]
            logger.debug(f"Permiso '{name}' (ID: {existing_perms[name].id}) ya existe en BD para tests.")

    if newly_created_perms:
        try:
            logger.info(f"Realizando flush para crear {len(newly_created_perms)} permisos faltantes...")
            db.flush()
            logger.info("Flush completado. Refrescando permisos nuevos...")
            for perm_obj in newly_created_perms:
                db.refresh(perm_obj)
                logger.info(f"Permiso '{perm_obj.nombre}' creado/refrescado con ID {perm_obj.id}.")
        except Exception as e:
            logger.critical(f"Error durante flush/refresh al crear permisos: {e}", exc_info=True)
            db.rollback()
            pytest.fail(f"Error crítico creando permisos faltantes: {e}")

    logger.debug(f"Fin fixture: test_permisos_definidos. Permisos asegurados: {len(permisos_dict)}.")
    if set(perm_names) != set(permisos_dict.keys()):
        missing = set(perm_names) - set(permisos_dict.keys())
        logger.critical(f"Error: Faltan permisos después de la ejecución de la fixture: {missing}")
        pytest.fail(f"Error crítico: Faltan permisos en la fixture: {missing}")

    return permisos_dict

def _ensure_rol_with_permissions(db: Session, rol_name: str, descripcion: str, required_perm_names: List[str], all_available_perms: Dict[str, Permiso]) -> Rol:
    logger.debug(f"Asegurando rol '{rol_name}' con {len(required_perm_names)} permisos requeridos...")
    rol = db.query(Rol).options(selectinload(Rol.permisos)).filter(Rol.nombre == rol_name).first()

    required_perm_objects: Set[Permiso] = set()
    for name in required_perm_names:
        perm_obj = all_available_perms.get(name)
        if not perm_obj: pytest.fail(f"Permiso base '{name}' no encontrado en all_available_perms para rol '{rol_name}'.")
        required_perm_objects.add(perm_obj)

    needs_db_interaction = False
    if not rol:
        logger.warning(f"Rol '{rol_name}' no encontrado. Creando...")
        rol = Rol(nombre=rol_name, descripcion=descripcion, permisos=list(required_perm_objects)) # type: ignore
        db.add(rol)
        needs_db_interaction = True
    else:
        logger.info(f"Rol '{rol_name}' (ID: {rol.id}) encontrado.")
        current_perm_objects = set(rol.permisos)
        if current_perm_objects != required_perm_objects:
            logger.warning(f"Rol '{rol_name}' (ID: {rol.id}) requiere actualización de permisos. Actuales: {len(current_perm_objects)}, Requeridos: {len(required_perm_objects)}.")
            rol.permisos = list(required_perm_objects)
            db.add(rol)
            needs_db_interaction = True
        else:
            logger.debug(f"Rol '{rol_name}' (ID: {rol.id}) ya tiene los {len(required_perm_objects)} permisos correctos.")

    if needs_db_interaction:
        try:
            db.flush()
            db.refresh(rol)
            if rol.permisos is not None:
                db.refresh(rol, attribute_names=['permisos'])
            logger.info(f"Rol '{rol_name}' (ID: {rol.id}) asegurado/actualizado con {len(rol.permisos)} permisos.")
        except Exception as e:
            logger.critical(f"Error en flush/refresh para rol '{rol_name}': {e}", exc_info=True)
            db.rollback(); pytest.fail(f"Error crítico asegurando rol '{rol_name}': {e}")

    final_perms_in_rol = {p.nombre for p in rol.permisos}
    if final_perms_in_rol != set(required_perm_names):
        missing = set(required_perm_names) - final_perms_in_rol
        extra = final_perms_in_rol - set(required_perm_names)
        error_msg = (f"Error Crítico en _ensure_rol_with_permissions para '{rol_name}': No tiene los permisos EXACTOS. "
                     f"Faltan: {missing if missing else 'Ninguno'}. Sobran: {extra if extra else 'Ninguno'}.")
        logger.critical(error_msg)
        pytest.fail(error_msg)

    logger.debug(f"Fin _ensure_rol_with_permissions para rol '{rol_name}' (ID: {rol.id}).")
    return rol

# ==============================================================================
# DEFINICIÓN DE ROLES SINCRONIZADA
# ==============================================================================

@pytest.fixture(scope="function")
def test_rol_admin(db: Session, test_permisos_definidos: Dict[str, Permiso]) -> Rol:
    """Rol 'admin' con 38 permisos (todos)."""
    all_perm_names = list(test_permisos_definidos.keys())
    return _ensure_rol_with_permissions(db, "admin", "Administrador con acceso total al sistema", all_perm_names, test_permisos_definidos)

@pytest.fixture(scope="function")
def test_rol_supervisor(db: Session, test_permisos_definidos: Dict[str, Permiso]) -> Rol:
    """Rol 'supervisor' con 34 permisos de gestión."""
    perm_names = [
        'administrar_catalogos', 'administrar_inventario_stock', 'administrar_inventario_tipos',
        'administrar_licencias', 'administrar_software_catalogo', 'administrar_usuarios',
        'aprobar_reservas', 'asignar_licencias', 'autorizar_movimientos', 'cancelar_movimientos',
        'crear_equipos', 'editar_documentos', 'editar_equipos', 'editar_mantenimientos',
        'editar_movimientos', 'eliminar_documentos', 'eliminar_equipos', 'eliminar_mantenimientos',
        'generar_reportes', 'gestionar_componentes', 'programar_mantenimientos',
        'registrar_movimientos', 'reservar_equipos', 'subir_documentos', 'ver_dashboard',
        'ver_documentos', 'ver_equipos', 'ver_inventario', 'ver_licencias', 'ver_mantenimientos',
        'ver_movimientos', 'ver_proveedores', 'ver_reservas', 'verificar_documentos'
    ]
    return _ensure_rol_with_permissions(db, "supervisor", "Supervisor con gestión operativa y de recursos", perm_names, test_permisos_definidos)

@pytest.fixture(scope="function")
def test_rol_tecnico(db: Session, test_permisos_definidos: Dict[str, Permiso]) -> Rol:
    """Rol 'tecnico' con 14 permisos operativos."""
    perm_names = [
        'editar_mantenimientos', 'gestionar_componentes', 'programar_mantenimientos',
        'registrar_movimientos', 'reservar_equipos', 'subir_documentos', 'ver_dashboard',
        'ver_documentos', 'ver_equipos', 'ver_inventario', 'ver_licencias',
        'ver_mantenimientos', 'ver_movimientos', 'ver_proveedores'
    ]
    return _ensure_rol_with_permissions(db, "tecnico", "Técnico de Mantenimiento o Soporte", perm_names, test_permisos_definidos)

@pytest.fixture(scope="function")
def test_rol_usuario_regular(db: Session, test_permisos_definidos: Dict[str, Permiso]) -> Rol:
    """Rol 'usuario_regular' con 11 permisos de consulta y autoservicio."""
    perm_names = [
        'reservar_equipos', 'subir_documentos', 'ver_dashboard', 'ver_documentos',
        'ver_equipos', 'ver_inventario', 'ver_licencias', 'ver_mantenimientos',
        'ver_movimientos', 'ver_proveedores', 'ver_reservas'
    ]
    return _ensure_rol_with_permissions(db, "usuario_regular", "Usuario Estándar para operaciones diarias y consulta", perm_names, test_permisos_definidos)

@pytest.fixture(scope="function")
def test_rol_auditor(db: Session, test_permisos_definidos: Dict[str, Permiso]) -> Rol:
    """Rol 'auditor' con 11 permisos de solo lectura y auditoría."""
    perm_names = [
        'generar_reportes', 'ver_auditoria', 'ver_dashboard', 'ver_documentos',
        'ver_equipos', 'ver_inventario', 'ver_licencias', 'ver_mantenimientos',
        'ver_movimientos', 'ver_proveedores', 'ver_reservas'
    ]
    return _ensure_rol_with_permissions(db, "auditor", "Auditor con permisos de solo lectura y consulta", perm_names, test_permisos_definidos)

@pytest.fixture(scope="function")
def test_rol_tester(db: Session, test_permisos_definidos: Dict[str, Permiso]) -> Rol:
    """Rol 'tester' con 36 permisos para pruebas funcionales."""
    perm_names = [
        'administrar_catalogos', 'administrar_inventario_stock', 'administrar_inventario_tipos', 'administrar_licencias',
        'administrar_roles', 'administrar_software_catalogo', 'administrar_usuarios', 'aprobar_reservas', 'asignar_licencias',
        'autorizar_movimientos', 'cancelar_movimientos', 'crear_equipos', 'editar_documentos', 'editar_equipos',
        'editar_mantenimientos', 'editar_movimientos', 'eliminar_documentos', 'eliminar_equipos', 'eliminar_mantenimientos',
        'generar_reportes', 'gestionar_componentes', 'programar_mantenimientos', 'registrar_movimientos', 'reservar_equipos',
        'subir_documentos', 'ver_auditoria', 'ver_dashboard', 'ver_documentos', 'ver_equipos', 'ver_inventario',
        'ver_licencias', 'ver_mantenimientos', 'ver_movimientos', 'ver_proveedores', 'ver_reservas', 'verificar_documentos'
    ]
    return _ensure_rol_with_permissions(db, "tester", "Rol para pruebas funcionales y de sistema", perm_names, test_permisos_definidos)


def _ensure_user(db: Session, username: str, password: str, rol: Rol, email: str | None = None) -> Usuario:
    logger.debug(f"Asegurando usuario '{username}' con rol '{rol.nombre}' (ID: {rol.id})")
    if not rol or not rol.id:
        pytest.fail(f"Rol inválido '{rol.nombre}' para usuario '{username}'.")

    user = db.query(Usuario).options(selectinload(Usuario.rol)).filter(Usuario.nombre_usuario == username).first()
    hashed_password_to_set = get_password_hash(password)
    
    final_email = email or f"{username}@fixture.example.com"

    if not user:
        logger.warning(f"Usuario '{username}' no encontrado. Creando con rol '{rol.nombre}'...")
        user = Usuario(
            nombre_usuario=username,
            email=final_email,
            rol_id=rol.id,
            hashed_password=hashed_password_to_set,
            requiere_cambio_contrasena=False,
            bloqueado=False,
            intentos_fallidos=0
        )
        db.add(user)
    else:
        logger.info(f"Usuario '{username}' (ID: {user.id}) encontrado.")
        if not verify_password(password, user.hashed_password):
            user.hashed_password = hashed_password_to_set
            db.add(user)
        if user.rol_id != rol.id or user.rol is None or user.rol.id != rol.id:
            user.rol_id = rol.id
            user.rol = rol
            db.add(user)
        if user.bloqueado:
            user.bloqueado = False
            db.add(user)
        if user.intentos_fallidos != 0:
            user.intentos_fallidos = 0
            db.add(user)
        if user.requiere_cambio_contrasena:
            user.requiere_cambio_contrasena = False
            db.add(user)
        if user.email != final_email:
            user.email = final_email
            db.add(user)

    try:
        db.flush()
        db.refresh(user)
        db.refresh(user, attribute_names=['rol'])
        if user.rol and user.rol.permisos is not None:
            db.refresh(user.rol, attribute_names=['permisos'])
        logger.info(f"Usuario '{username}' (ID: {user.id}) flusheado/refrescado. Rol: '{user.rol.nombre if user.rol else 'N/A'}'.")
    except Exception as e:
        logger.critical(f"Error en flush/refresh para usuario '{username}': {e}", exc_info=True)
        db.rollback()
        pytest.fail(f"Error crítico en flush/refresh para usuario '{username}': {e}")

    if user.rol is None or user.rol.id != rol.id:
        pytest.fail(f"Rol para usuario '{username}' no se asignó/refrescó correctamente. Esperado: '{rol.nombre}', Obtenido: '{user.rol.nombre if user.rol else 'None'}'.")
    logger.info(f"Verificación OK: Usuario '{username}' (ID: {user.id}) listo con rol '{user.rol.nombre}' (ID: {user.rol.id}).")
    return user


@pytest.fixture(scope="function")
def test_usuario_regular_fixture(db: Session, test_rol_usuario_regular: Rol) -> Usuario:
    return _ensure_user(db, "usuario_regular", TEST_USER_REGULAR_PASSWORD, test_rol_usuario_regular)

@pytest.fixture(scope="function")
def test_admin_fixture(db: Session, test_rol_admin: Rol) -> Usuario:
    return _ensure_user(db, "admin", TEST_ADMIN_PASSWORD, test_rol_admin)

@pytest.fixture(scope="function")
def test_supervisor_fixture(db: Session, test_rol_supervisor: Rol) -> Usuario:
    return _ensure_user(db, "supervisor", TEST_SUPERVISOR_PASSWORD, test_rol_supervisor)

@pytest.fixture(scope="function")
def test_tecnico_fixture(db: Session, test_rol_tecnico: Rol) -> Usuario:
    return _ensure_user(db, "tecnico", TEST_TECNICO_PASSWORD, test_rol_tecnico)

@pytest.fixture(scope="function")
def test_auditor_fixture(db: Session, test_rol_auditor: Rol) -> Usuario:
    return _ensure_user(db, "auditor", TEST_AUDITOR_PASSWORD, test_rol_auditor)

@pytest.fixture(scope="function")
def test_tester_fixture(db: Session, test_rol_tester: Rol) -> Usuario:
    return _ensure_user(db, "tester_functional", TEST_TESTER_PASSWORD, test_rol_tester)

@pytest_asyncio.fixture(scope="function")
async def auth_token_usuario_regular(client: AsyncClient, test_usuario_regular_fixture: Usuario) -> str:
    token = await get_auth_token(client, test_usuario_regular_fixture.nombre_usuario, TEST_USER_REGULAR_PASSWORD)
    if not token:
        pytest.fail(f"No se pudo obtener token para '{test_usuario_regular_fixture.nombre_usuario}'.")
    return token

@pytest_asyncio.fixture(scope="function")
async def auth_token_admin(client: AsyncClient, test_admin_fixture: Usuario) -> str:
    token = await get_auth_token(client, test_admin_fixture.nombre_usuario, TEST_ADMIN_PASSWORD)
    if not token:
        pytest.fail(f"No se pudo obtener token para '{test_admin_fixture.nombre_usuario}'.")
    return token

@pytest_asyncio.fixture(scope="function")
async def auth_token_supervisor(client: AsyncClient, test_supervisor_fixture: Usuario) -> str:
    token = await get_auth_token(client, test_supervisor_fixture.nombre_usuario, TEST_SUPERVISOR_PASSWORD)
    if not token:
        pytest.fail(f"No se pudo obtener token para '{test_supervisor_fixture.nombre_usuario}'.")
    return token

@pytest_asyncio.fixture(scope="function")
async def auth_token_tecnico(client: AsyncClient, test_tecnico_fixture: Usuario) -> str:
    token = await get_auth_token(client, test_tecnico_fixture.nombre_usuario, TEST_TECNICO_PASSWORD)
    if not token:
        pytest.fail(f"No se pudo obtener token para '{test_tecnico_fixture.nombre_usuario}'.")
    return token

@pytest_asyncio.fixture(scope="function")
async def auth_token_auditor(client: AsyncClient, test_auditor_fixture: Usuario) -> str:
    token = await get_auth_token(client, test_auditor_fixture.nombre_usuario, TEST_AUDITOR_PASSWORD)
    if not token:
        pytest.fail(f"No se pudo obtener token para '{test_auditor_fixture.nombre_usuario}'.")
    return token

@pytest_asyncio.fixture(scope="function")
async def auth_token_tester(client: AsyncClient, test_tester_fixture: Usuario) -> str:
    token = await get_auth_token(client, test_tester_fixture.nombre_usuario, TEST_TESTER_PASSWORD)
    if not token:
        pytest.fail(f"No se pudo obtener token para '{test_tester_fixture.nombre_usuario}'.")
    return token

@pytest.fixture(scope="function")
def test_estado_disponible(db: Session) -> EstadoEquipo:
    logger.debug("Inicio fixture: test_estado_disponible")
    nombre_estado = "Disponible"
    estado = db.query(EstadoEquipo).filter(EstadoEquipo.nombre == nombre_estado).first()
    if not estado:
        estado = EstadoEquipo(nombre=nombre_estado, permite_movimientos=True, color_hex="#4CAF50", es_estado_final=False) # type: ignore
        db.add(estado); db.flush(); db.refresh(estado)
    return estado

@pytest.fixture(scope="function")
def test_estado_en_uso(db: Session) -> EstadoEquipo:
    logger.debug("Inicio fixture: test_estado_en_uso")
    nombre_estado = "En Uso"
    estado = db.query(EstadoEquipo).filter(EstadoEquipo.nombre == nombre_estado).first()
    if not estado:
        estado = EstadoEquipo(nombre=nombre_estado, permite_movimientos=True, color_hex="#2196F3", es_estado_final=False) # type: ignore
        db.add(estado); db.flush(); db.refresh(estado)
    return estado

@pytest.fixture(scope="function")
def test_estado_prestado(db: Session) -> EstadoEquipo:
    logger.debug("Inicio fixture: test_estado_prestado")
    nombre_estado = "Prestado"
    estado = db.query(EstadoEquipo).filter(EstadoEquipo.nombre == nombre_estado).first()
    if not estado:
        estado = EstadoEquipo(nombre=nombre_estado, descripcion="Fuera de las instalaciones temporalmente", permite_movimientos=False, requiere_autorizacion=False, color_hex="#FF9800", es_estado_final=False) # type: ignore
        db.add(estado); db.flush(); db.refresh(estado)
    return estado

@pytest.fixture(scope="function")
def test_estado_mantenimiento(db: Session) -> EstadoEquipo:
    logger.debug("Inicio fixture: test_estado_mantenimiento")
    nombre_estado = "En Mantenimiento"
    estado = db.query(EstadoEquipo).filter(EstadoEquipo.nombre == nombre_estado).first()
    if not estado:
        estado = EstadoEquipo(nombre=nombre_estado, descripcion="En proceso de mantenimiento preventivo/correctivo", permite_movimientos=False, requiere_autorizacion=False, color_hex="#FFC107", es_estado_final=False) # type: ignore
        db.add(estado); db.flush(); db.refresh(estado)
    return estado

@pytest.fixture(scope="function")
def test_tipo_doc_factura(db: Session) -> TipoDocumento:
    logger.debug("Inicio fixture: test_tipo_doc_factura")
    nombre_tipo = "Factura Compra"
    tipo = db.query(TipoDocumento).filter(TipoDocumento.nombre == nombre_tipo).first()
    if not tipo:
        tipo = TipoDocumento(nombre=nombre_tipo, requiere_verificacion=True, formato_permitido=['pdf', 'jpg', 'png', 'xml']) # type: ignore
        db.add(tipo); db.flush(); db.refresh(tipo)
    return tipo

@pytest.fixture(scope="function")
def test_tipo_doc_manual(db: Session) -> TipoDocumento:
    logger.debug("Inicio fixture: test_tipo_doc_manual")
    nombre_tipo = "Manual Usuario"
    tipo = db.query(TipoDocumento).filter(TipoDocumento.nombre == nombre_tipo).first()
    if not tipo:
        tipo = TipoDocumento(nombre=nombre_tipo, requiere_verificacion=False, formato_permitido=['pdf', 'docx']) # type: ignore
        db.add(tipo); db.flush(); db.refresh(tipo)
    return tipo

@pytest.fixture(scope="function")
def test_proveedor(db: Session) -> Proveedor:
    logger.debug("Inicio fixture: test_proveedor")
    nombre_prov = "Proveedor Test Fixture"
    rnc_prov = f"RNC-FIXTURE-{uuid4().hex[:5].upper()}"
    prov = db.query(Proveedor).filter(Proveedor.rnc == rnc_prov).first()
    if not prov:
        prov_by_name = db.query(Proveedor).filter(Proveedor.nombre == nombre_prov).first()
        if prov_by_name:
            prov = prov_by_name
            if prov.rnc != rnc_prov:
                prov.rnc = rnc_prov
                db.add(prov)
        else:
            prov = Proveedor(nombre=nombre_prov, rnc=rnc_prov, contacto="contacto@proveedorfixture.com", descripcion="Proveedor para fixtures de prueba.") # type: ignore
            db.add(prov)
        db.flush()
        db.refresh(prov)
    return prov

def generate_test_serie(prefix: str = "TEST") -> str:
    part1 = prefix.upper().ljust(3, 'X')[:3]
    part2 = uuid4().hex[:4].upper()
    part3 = uuid4().hex[:4].upper()
    return f"{part1}-{part2}-{part3}"

@pytest.fixture(scope="function")
def test_equipo_reservable(db: Session, test_estado_disponible: EstadoEquipo, test_proveedor: Proveedor) -> Equipo:
    logger.debug("Inicio fixture: test_equipo_reservable")
    serie = generate_test_serie("RSV")
    nombre_equipo = f"Proyector Test {serie}"
    equipo = db.query(Equipo).filter(Equipo.numero_serie == serie).first()
    if not equipo:
        equipo = Equipo(nombre=nombre_equipo, numero_serie=serie, estado_id=test_estado_disponible.id,
                        marca="Epson Test", modelo="XYZ-100", proveedor_id=test_proveedor.id,
                        fecha_adquisicion=date.today() - timedelta(days=30), valor_adquisicion=Decimal("450.99")) # type: ignore
        db.add(equipo)
    else:
        equipo.estado_id = test_estado_disponible.id; equipo.nombre = nombre_equipo; db.add(equipo) # type: ignore
    db.flush(); db.refresh(equipo)
    return equipo

@pytest.fixture(scope="function")
def test_equipo_principal(db: Session, test_estado_disponible: EstadoEquipo) -> Equipo:
    logger.debug("Inicio fixture: test_equipo_principal")
    serie = generate_test_serie("PADRE")
    equipo = db.query(Equipo).filter(Equipo.numero_serie == serie).first()
    if not equipo:
        equipo = Equipo(nombre=f"Equipo Principal Test {serie}", numero_serie=serie, estado_id=test_estado_disponible.id) # type: ignore
        db.add(equipo); db.flush(); db.refresh(equipo)
    return equipo

@pytest.fixture(scope="function")
def test_componente_ram(db: Session, test_estado_disponible: EstadoEquipo) -> Equipo:
    logger.debug("Inicio fixture: test_componente_ram")
    serie_ram = generate_test_serie("RAM")
    equipo_ram_obj = db.query(Equipo).filter(Equipo.numero_serie == serie_ram).first()
    if not equipo_ram_obj:
        equipo_ram_obj = Equipo(
            nombre=f"Modulo RAM Test {serie_ram}", numero_serie=serie_ram,
            estado_id=test_estado_disponible.id, marca="Kingston", modelo="DDR4-SODIMM-8GB" # type: ignore
        )
        db.add(equipo_ram_obj); db.flush(); db.refresh(equipo_ram_obj)
    return equipo_ram_obj

@pytest.fixture(scope="function")
def test_notificacion_user(db: Session, test_usuario_regular_fixture: Usuario) -> Notificacion:
    logger.debug("Inicio fixture: test_notificacion_user")
    notif_msg = f"Mensaje test para {test_usuario_regular_fixture.nombre_usuario} - {uuid4().hex[:4]}"
    notif = db.query(Notificacion).filter(Notificacion.usuario_id == test_usuario_regular_fixture.id, Notificacion.mensaje == notif_msg).first() # type: ignore
    if not notif:
        notif = Notificacion(usuario_id=test_usuario_regular_fixture.id, mensaje=notif_msg, tipo=TipoNotificacionEnum.INFO.value, leido=False) # type: ignore
        db.add(notif); db.flush(); db.refresh(notif)
    elif notif.leido:
        notif.leido = False; db.add(notif); db.flush(); db.refresh(notif) # type: ignore
    return notif

@pytest.fixture(scope="function")
def test_documento_pendiente(db: Session, test_equipo_reservable: Equipo, test_tipo_doc_factura: TipoDocumento, test_usuario_regular_fixture: Usuario) -> Documentacion:
    logger.debug("Inicio fixture: test_documento_pendiente")
    titulo_doc = f"Factura Pendiente Test {test_equipo_reservable.numero_serie} - {uuid4().hex[:4]}"
    doc = db.query(Documentacion).filter(Documentacion.titulo == titulo_doc).first() # type: ignore
    if not doc:
        doc = Documentacion(
            equipo_id=test_equipo_reservable.id, tipo_documento_id=test_tipo_doc_factura.id, # type: ignore
            titulo=titulo_doc, enlace=f"/uploads/fake_test_docs/{uuid4().hex[:8]}.pdf",
            nombre_archivo=f"fact_test_{uuid4().hex[:4]}.pdf", mime_type="application/pdf", tamano_bytes=102400,
            subido_por=test_usuario_regular_fixture.id, estado=EstadoDocumentoEnum.PENDIENTE.value # type: ignore
        )
        db.add(doc); db.flush(); db.refresh(doc)
    elif doc.estado != EstadoDocumentoEnum.PENDIENTE.value: # type: ignore
        doc.estado = EstadoDocumentoEnum.PENDIENTE.value; db.add(doc); db.flush(); db.refresh(doc) # type: ignore
    return doc

@pytest.fixture(scope="function")
def tipo_mantenimiento_preventivo(db: Session) -> TipoMantenimiento:
    logger.debug("Inicio fixture: tipo_mantenimiento_preventivo")
    nombre_tipo = "Preventivo Test Fixture"
    tipo = db.query(TipoMantenimiento).filter(TipoMantenimiento.nombre == nombre_tipo).first()
    if not tipo:
        tipo = TipoMantenimiento(nombre=nombre_tipo, es_preventivo=True, periodicidad_dias=90, descripcion="Mantenimiento preventivo de prueba.") # type: ignore
        db.add(tipo); db.flush(); db.refresh(tipo)
    return tipo

@pytest.fixture(scope="function")
def tipo_mantenimiento_correctivo(db: Session) -> TipoMantenimiento:
    logger.debug("Inicio fixture: tipo_mantenimiento_correctivo")
    nombre_tipo = "Correctivo Test Fixture"
    tipo = db.query(TipoMantenimiento).filter(TipoMantenimiento.nombre == nombre_tipo).first()
    if not tipo:
        tipo = TipoMantenimiento(nombre=nombre_tipo, es_preventivo=False, descripcion="Mantenimiento correctivo de prueba.") # type: ignore
        db.add(tipo); db.flush(); db.refresh(tipo)
    return tipo

@pytest.fixture(scope="function")
def proveedor_servicio_externo(db: Session) -> Proveedor:
    logger.debug("Inicio fixture: proveedor_servicio_externo")
    nombre_prov = "Servicios Externos Test Fixture"
    rnc_prov = f"RNCEXT-{uuid4().hex[:6].upper()}"
    prov = db.query(Proveedor).filter(Proveedor.rnc == rnc_prov).first()
    if not prov:
        prov_by_name = db.query(Proveedor).filter(Proveedor.nombre == nombre_prov).first()
        if prov_by_name:
            prov = prov_by_name
            if prov.rnc != rnc_prov:
                prov.rnc = rnc_prov
                db.add(prov)
        else:
            prov = Proveedor(nombre=nombre_prov, rnc=rnc_prov, contacto="serv@externos.test") # type: ignore
            db.add(prov)
        db.flush()
        db.refresh(prov)
    return prov

@pytest.fixture(scope="function")
def tipo_item_toner(db: Session) -> TipoItemInventario:
    logger.debug("Inicio fixture: tipo_item_toner")
    nombre_item = "Toner Test Fixture"
    sku_test = f"TONER-FX-{nombre_item.replace(' ', '_').upper()}-{uuid4().hex[:4]}"
    item = db.query(TipoItemInventario).filter(TipoItemInventario.sku == sku_test).first()
    if not item:
        item = TipoItemInventario(nombre=nombre_item, categoria="Consumible", unidad_medida=UnidadMedidaEnum.UNIDAD.value, sku=sku_test, stock_minimo=2) # type: ignore
        db.add(item)
        db.flush()
        db.refresh(item)
        logger.info(f"Creado TipoItemInventario '{nombre_item}' con ID {item.id} y SKU {item.sku}")
    return item

# tests/conftest.py

@pytest.fixture(scope="function")
async def stock_inicial_toner(db: Session, tipo_item_toner: TipoItemInventario) -> InventarioStock:
    """
    Asegura que haya un registro de stock inicial predecible para un item
    en una ubicación y lote ('N/A') específicos.
    Es idempotente: crea el registro si no existe, o lo actualiza si ya existe.
    """
    logger.debug("Inicio fixture: stock_inicial_toner")
    ubicacion_test = "Almacén Principal Toner Fixture"
    lote_defecto = "N/A" # Usar el valor por defecto que definimos en la DB
    cantidad_inicial = 10
    costo_inicial = Decimal("25.50")
    
    # --- CORRECCIÓN CLAVE ---
    # Buscamos el registro usando el lote por defecto, no None.
    stock_record = db.query(InventarioStock).filter(
        InventarioStock.tipo_item_id == tipo_item_toner.id,
        InventarioStock.ubicacion == ubicacion_test,
        InventarioStock.lote == lote_defecto 
    ).first()

    if stock_record:
        # Si ya existe, nos aseguramos de que tenga los valores correctos para la prueba
        stock_record.cantidad_actual = cantidad_inicial
        stock_record.costo_promedio_ponderado = costo_inicial
        stock_record.ultima_actualizacion = datetime.now(timezone.utc)
    else:
        # Si no existe, lo creamos con el lote correcto
        stock_record = InventarioStock(
            tipo_item_id=tipo_item_toner.id,
            ubicacion=ubicacion_test,
            lote=lote_defecto,  # <-- Se establece el lote a 'N/A'
            cantidad_actual=cantidad_inicial,
            costo_promedio_ponderado=costo_inicial,
            ultima_actualizacion=datetime.now(timezone.utc)
        )
    
    db.add(stock_record)
    db.flush()
    db.refresh(stock_record)
    logger.info(f"Fixture stock_inicial_toner: Stock ID {stock_record.id} con cantidad {stock_record.cantidad_actual} en lote '{stock_record.lote}'.")
    return stock_record

@pytest.fixture(scope="function")
def software_office(db: Session) -> SoftwareCatalogo:
    logger.debug("Inicio fixture: software_office")
    nombre_sw = "Microsoft Office Test Fixture"
    version_sw = "2021 Pro"
    sw = db.query(SoftwareCatalogo).filter(SoftwareCatalogo.nombre == nombre_sw, SoftwareCatalogo.version == version_sw).first() # type: ignore
    if not sw:
        sw = SoftwareCatalogo(nombre=nombre_sw, version=version_sw, tipo_licencia=TipoLicenciaSoftwareEnum.PERPETUA.value, metrica_licenciamiento=MetricaLicenciamientoEnum.POR_DISPOSITIVO.value, fabricante="Microsoft Test", categoria="Ofimática") # type: ignore
        db.add(sw); db.flush(); db.refresh(sw)
    return sw

@pytest.fixture(scope="function")
def software_win(db: Session) -> SoftwareCatalogo:
    logger.debug("Inicio fixture: software_win")
    nombre_sw = "Windows Test Pro Fixture"
    version_sw = "11 Enterprise"
    sw = db.query(SoftwareCatalogo).filter(SoftwareCatalogo.nombre == nombre_sw, SoftwareCatalogo.version == version_sw).first() # type: ignore
    if not sw:
        sw = SoftwareCatalogo(nombre=nombre_sw, version=version_sw, fabricante="Microsoft Test", categoria="Sistema Operativo", tipo_licencia=TipoLicenciaSoftwareEnum.OEM.value, metrica_licenciamiento=MetricaLicenciamientoEnum.POR_DISPOSITIVO.value) # type: ignore
        db.add(sw); db.flush(); db.refresh(sw)
    return sw

@pytest.fixture(scope="function")
def licencia_office_disponible(db: Session, software_office: SoftwareCatalogo, test_proveedor: Proveedor) -> LicenciaSoftware:
    logger.debug("Inicio fixture: licencia_office_disponible")
    nota_fixture = f"Fixture Test Office 5 Licencias - {software_office.id}-{uuid4().hex[:4]}"
    lic = db.query(LicenciaSoftware).options(selectinload(LicenciaSoftware.asignaciones)).filter(LicenciaSoftware.notas == nota_fixture).first() # type: ignore
    cantidad_total_test = 5
    if lic:
        logger.info(f"LicenciaSoftware (notas: '{nota_fixture}') encontrada. ID: {lic.id}. Limpiando asignaciones previas...")
        if lic.asignaciones: # type: ignore
            delete_asig_stmt = delete(AsignacionLicencia).where(AsignacionLicencia.licencia_id == lic.id) # type: ignore
            db.execute(delete_asig_stmt); db.flush()
            db.refresh(lic, attribute_names=['asignaciones'])
    else:
        logger.info(f"LicenciaSoftware (notas: '{nota_fixture}') no encontrada. Creando nueva...")
        lic = LicenciaSoftware(software_catalogo_id=software_office.id, fecha_adquisicion=date.today() - timedelta(days=30), cantidad_total=cantidad_total_test, notas=nota_fixture, proveedor_id=test_proveedor.id) # type: ignore
        db.add(lic); db.flush(); db.refresh(lic)
    
    lic.cantidad_total = cantidad_total_test # type: ignore
    lic.cantidad_disponible = cantidad_total_test # type: ignore
    lic.costo_adquisicion = Decimal("1250.75") # type: ignore
    lic.fecha_expiracion = None # type: ignore
    db.add(lic); db.flush(); db.refresh(lic)
    return lic

@pytest.fixture(scope="function")
async def equipo_sin_licencia(db: Session, test_estado_disponible: EstadoEquipo) -> Equipo:
    logger.debug("Inicio fixture: equipo_sin_licencia")
    serie = generate_test_serie("NOLIC")
    equipo = db.query(Equipo).filter(Equipo.numero_serie == serie).first()
    if not equipo:
        equipo = Equipo(nombre=f"Equipo Sin Licencia Test {serie}", numero_serie=serie, estado_id=test_estado_disponible.id) # type: ignore
        db.add(equipo); db.flush(); db.refresh(equipo)
    return equipo

@pytest.fixture(scope="function")
async def create_test_rol(db: Session, test_permisos_definidos: Dict[str, Permiso]) -> Rol:
    logger.debug("Inicio fixture: create_test_rol")
    permiso_ver_equipos = test_permisos_definidos.get("ver_equipos")
    if not permiso_ver_equipos:
        pytest.fail("Fixture 'test_permisos_definidos' no proporcionó 'ver_equipos'.")
    rol_name = f"rol_simple_test_{uuid4().hex[:6]}"
    rol = db.query(Rol).options(selectinload(Rol.permisos)).filter(Rol.nombre == rol_name).first()
    if not rol:
        rol = Rol(nombre=rol_name, descripcion="Rol para GET/DELETE test de roles_permisos") # type: ignore
        db.add(rol)
        db.flush()
        db.refresh(rol)
        rol.permisos.append(permiso_ver_equipos) # type: ignore
        db.add(rol)
        db.flush()
        db.refresh(rol, attribute_names=['permisos'])
    elif not rol.permisos or permiso_ver_equipos not in rol.permisos: # type: ignore
        rol.permisos.append(permiso_ver_equipos) # type: ignore
        db.add(rol)
        db.flush()
        db.refresh(rol, attribute_names=['permisos'])
    return rol

@pytest.fixture(scope="function")
async def create_test_user_directly(db: Session, test_rol_usuario_regular: Rol) -> Usuario:
    logger.debug("Inicio fixture: create_test_user_directly")
    username = f"get_user_direct_{uuid4().hex[:6]}"
    email = f"{username}@example.com"
    if not test_rol_usuario_regular or not test_rol_usuario_regular.id:
        pytest.fail("Fixture 'test_rol_usuario_regular' inválida.")
    user = Usuario(
        nombre_usuario=username,
        email=email,
        hashed_password=get_password_hash("TestPasswordDirect123!"),
        rol_id=test_rol_usuario_regular.id,
        requiere_cambio_contrasena=False,
        bloqueado=False
    ) # type: ignore
    db.add(user)
    db.flush()
    db.refresh(user)
    db.refresh(user, attribute_names=['rol'])
    if not user.rol:
        pytest.fail(f"Rol no cargado para usuario directo '{username}' después de refresh.")
    return user

@pytest.fixture(scope="function")
async def reserva_pendiente(db: Session, test_usuario_regular_fixture: Usuario, test_equipo_reservable: Equipo) -> ReservaEquipo:
    logger.debug("Inicio fixture: reserva_pendiente")
    start_time = datetime.now(timezone.utc) + timedelta(days=7, hours=1)
    end_time = start_time + timedelta(hours=2)
    
    delete_stmt = delete(ReservaEquipo).where(
        ReservaEquipo.equipo_id == test_equipo_reservable.id, # type: ignore
        text("tstzrange(fecha_hora_inicio, fecha_hora_fin, '()') && tstzrange(:start, :end, '()')"),
        ReservaEquipo.estado.in_([EstadoReservaEnum.CONFIRMADA.value, EstadoReservaEnum.PENDIENTE_APROBACION.value, EstadoReservaEnum.EN_CURSO.value, 'Solicitada'])
    )
    db.execute(delete_stmt, {'start': start_time, 'end': end_time})
    db.flush()

    reserva = ReservaEquipo(
        equipo_id=test_equipo_reservable.id,
        usuario_solicitante_id=test_usuario_regular_fixture.id, # type: ignore
        fecha_hora_inicio=start_time,
        fecha_hora_fin=end_time,
        estado=EstadoReservaEnum.PENDIENTE_APROBACION.value,
        proposito=f"Reserva Pendiente Test {uuid4().hex[:4]}"
    ) # type: ignore
    db.add(reserva); db.flush(); db.refresh(reserva)
    logger.info(f"Creada reserva_pendiente ID {reserva.id} para equipo {reserva.equipo_id}")
    return reserva

@pytest.fixture
def test_proveedor_para_borrar(db: Session) -> Proveedor:
    """Crea un proveedor único y no utilizado, seguro para ser borrado."""
    nombre_unico = f"Proveedor Borrable {uuid4().hex[:8]}"
    rnc_unico = f"RNC-DEL-{uuid4().hex[:8].upper()}"
    prov = Proveedor(nombre=nombre_unico, rnc=rnc_unico)
    db.add(prov)
    db.flush()
    db.refresh(prov)
    return prov

@pytest.fixture
def test_equipo_para_borrar(db: Session, test_estado_disponible: EstadoEquipo) -> Equipo:
    """Crea un equipo único y no utilizado, con un formato de serie válido."""
    serie_unica = f"DEL-{uuid4().hex[:4].upper()}-{uuid4().hex[:4].upper()}"
    equipo = Equipo(
        nombre=f"Equipo Borrable {serie_unica}",
        numero_serie=serie_unica,
        estado_id=test_estado_disponible.id
    )
    db.add(equipo)
    db.flush()
    db.refresh(equipo)
    return equipo

@pytest.fixture
def test_tipo_doc_para_borrar(db: Session) -> TipoDocumento:
    """Crea un tipo de documento único y no utilizado, seguro para ser borrado."""
    tipo_doc = TipoDocumento(
        nombre=f"Tipo Doc Borrable {uuid4().hex[:8]}"
    )
    db.add(tipo_doc)
    db.flush()
    db.refresh(tipo_doc)
    return tipo_doc

@pytest.fixture
def test_rol_para_borrar(db: Session) -> Rol:
    """Crea un rol simple y sin usuarios, seguro para ser borrado."""
    rol = Rol(nombre=f"Rol Borrable {uuid4().hex[:8]}")
    db.add(rol)
    db.flush()
    db.refresh(rol)
    return rol

@pytest.fixture
def test_reserva_para_cancelar(db: Session, test_equipo_reservable: Equipo, test_usuario_regular_fixture: Usuario) -> ReservaEquipo:
    """Crea una reserva básica que puede ser cancelada."""
    from datetime import datetime, timedelta, timezone
    reserva = ReservaEquipo(
        equipo_id=test_equipo_reservable.id,
        usuario_solicitante_id=test_usuario_regular_fixture.id,
        fecha_hora_inicio=datetime.now(timezone.utc) + timedelta(days=50),
        fecha_hora_fin=datetime.now(timezone.utc) + timedelta(days=50, hours=1),
        proposito="Reserva para test de cancelación"
    )
    db.add(reserva)
    db.flush()
    db.refresh(reserva)
    return reserva
