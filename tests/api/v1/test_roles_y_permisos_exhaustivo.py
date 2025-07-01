import pytest
from httpx import AsyncClient
from fastapi import status
from uuid import uuid4
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import (
    InventarioMovimiento,
    InventarioStock,
    Usuario,
    TipoItemInventario,
    TipoDocumento # Importar TipoDocumento
)
from app.schemas.enums import TipoMovimientoInvEnum

# Marcar todos los tests como asíncronos
pytestmark = pytest.mark.asyncio


@pytest.fixture(scope="function")
async def all_auth_tokens(
    auth_token_usuario_regular: str,
    auth_token_tecnico: str,
    auth_token_supervisor: str,
    auth_token_auditor: str,
) -> dict[str, str]:
    """
    Crea un diccionario de todos los tokens de autenticación para evitar
    el problema del event loop con request.getfixturevalue.
    """
    return {
        "auth_token_usuario_regular": auth_token_usuario_regular,
        "auth_token_tecnico": auth_token_tecnico,
        "auth_token_supervisor": auth_token_supervisor,
        "auth_token_auditor": auth_token_auditor,
    }

@pytest.fixture(scope="function")
def movimiento_para_pruebas(
    db: Session,
    stock_inicial_toner: InventarioStock,
    test_usuario_regular_fixture: Usuario
) -> InventarioMovimiento:
    """
    Crea un movimiento de inventario básico para obtener un ID válido en las pruebas.
    Esta fixture es local para resolver la dependencia del test parametrizado.
    """
    movimiento = InventarioMovimiento(
        tipo_item_id=stock_inicial_toner.tipo_item_id,
        tipo_movimiento=TipoMovimientoInvEnum.AJUSTE_POSITIVO.value,
        cantidad=1,
        ubicacion_destino=stock_inicial_toner.ubicacion,
        usuario_registrador=test_usuario_regular_fixture,
        motivo_ajuste="Movimiento para test de permisos"
    )
    db.add(movimiento)
    db.flush()
    db.refresh(movimiento)
    return movimiento

# FIX 1: Crear una fixture para un tipo de documento que NO esté en uso
@pytest.fixture(scope="function")
def tipo_documento_para_borrar(db: Session) -> TipoDocumento:
    """Crea un tipo de documento único y no utilizado, seguro para ser borrado."""
    tipo_doc = TipoDocumento(
        nombre=f"Doc Borrable {uuid4().hex[:6]}",
        requiere_verificacion=False
    )
    db.add(tipo_doc)
    db.flush()
    db.refresh(tipo_doc)
    return tipo_doc


# --- Datos de Prueba para Permisos ---

# Estructura: (rol_fixture, http_method, endpoint, expected_status_code, payload_data (opcional))
permission_tests_data = [
    # --- Gestión de Catálogos (Proveedores) ---
    ("auth_token_usuario_regular", "POST", "/proveedores/", status.HTTP_403_FORBIDDEN, {"nombre": f"Prov-Test-{uuid4().hex[:4]}"}),
    ("auth_token_tecnico", "POST", "/proveedores/", status.HTTP_403_FORBIDDEN, {"nombre": f"Prov-Test-{uuid4().hex[:4]}"}),
    ("auth_token_supervisor", "POST", "/proveedores/", status.HTTP_201_CREATED, {"nombre": f"Prov-Test-{uuid4().hex[:4]}"}),
    ("auth_token_usuario_regular", "DELETE", "/proveedores/{id}", status.HTTP_403_FORBIDDEN, None),
    ("auth_token_tecnico", "DELETE", "/proveedores/{id}", status.HTTP_403_FORBIDDEN, None),
    ("auth_token_supervisor", "DELETE", "/proveedores/{id}", status.HTTP_200_OK, None),

    # --- Gestión de Catálogos (Tipos de Documento) ---
    ("auth_token_usuario_regular", "POST", "/catalogos/tipos-documento/", status.HTTP_403_FORBIDDEN, {"nombre": f"Doc-Test-{uuid4().hex[:4]}"}),
    ("auth_token_supervisor", "POST", "/catalogos/tipos-documento/", status.HTTP_201_CREATED, {"nombre": f"Doc-Test-{uuid4().hex[:4]}"}),
    ("auth_token_usuario_regular", "DELETE", "/catalogos/tipos-documento/{id}", status.HTTP_403_FORBIDDEN, None),
    ("auth_token_supervisor", "DELETE", "/catalogos/tipos-documento/{id}", status.HTTP_200_OK, None),
    
    # --- Eliminación de Equipos ---
    ("auth_token_usuario_regular", "DELETE", "/equipos/{id}", status.HTTP_403_FORBIDDEN, None),
    ("auth_token_tecnico", "DELETE", "/equipos/{id}", status.HTTP_403_FORBIDDEN, None),
    ("auth_token_supervisor", "DELETE", "/equipos/{id}", status.HTTP_200_OK, None),
    
    # --- Gestión de Usuarios (el más restrictivo) ---
    # FIX 2: Usar una contraseña válida que cumpla con la longitud mínima.
    ("auth_token_usuario_regular", "POST", "/usuarios/", status.HTTP_403_FORBIDDEN, {"nombre_usuario": "test", "password": "ValidPass123!", "rol_id": "uuid"}),
    ("auth_token_tecnico", "POST", "/usuarios/", status.HTTP_403_FORBIDDEN, {"nombre_usuario": "test", "password": "ValidPass123!", "rol_id": "uuid"}),
    ("auth_token_supervisor", "POST", "/usuarios/", status.HTTP_201_CREATED, {"nombre_usuario": "test", "password": "ValidPass123!", "rol_id": "uuid"}),

    # --- Acceso de solo lectura para Auditor ---
    # FIX 3: El auditor no debe poder ver usuarios, el resultado correcto es 403.
    ("auth_token_auditor", "GET", "/usuarios/", status.HTTP_403_FORBIDDEN, None),
    ("auth_token_auditor", "POST", "/equipos/", status.HTTP_403_FORBIDDEN, {"nombre": "test", "numero_serie": "ABC-123-XYZ"}),
    ("auth_token_auditor", "DELETE", "/equipos/{id}", status.HTTP_403_FORBIDDEN, None),
    ("auth_token_auditor", "GET", "/auditoria/", status.HTTP_200_OK, None),
]

@pytest.mark.parametrize("rol_fixture, http_method, endpoint, expected_status, payload", permission_tests_data)
async def test_permissions_matrix(
    client: AsyncClient,
    rol_fixture: str,
    http_method: str,
    endpoint: str,
    expected_status: int,
    payload: dict | None,
    # Fixtures de conftest para crear objetos que se puedan eliminar/actualizar
    all_auth_tokens: dict[str, str],
    test_equipo_principal,
    test_proveedor,
    test_tipo_doc_factura,
    movimiento_para_pruebas,
    test_rol_usuario_regular,
    tipo_documento_para_borrar: TipoDocumento # FIX 1
):
    """
    Test parametrizado que verifica la matriz de permisos para diferentes roles.
    """
    auth_token = all_auth_tokens[rol_fixture]
    headers = {"Authorization": f"Bearer {auth_token}"}

    # Reemplazar placeholders en el endpoint con IDs reales de los fixtures
    if "{id}" in endpoint:
        if "proveedores" in endpoint:
            endpoint = endpoint.format(id=test_proveedor.id)
        elif "tipos-documento" in endpoint:
            # FIX 1: Usar la fixture del documento borrable para el test de DELETE
            if http_method == 'DELETE':
                endpoint = endpoint.format(id=tipo_documento_para_borrar.id)
            else:
                endpoint = endpoint.format(id=test_tipo_doc_factura.id)
        elif "equipos" in endpoint:
            endpoint = endpoint.format(id=test_equipo_principal.id)
        elif "movimientos" in endpoint:
             endpoint = endpoint.format(id=movimiento_para_pruebas.id)
    
    # Reemplazar placeholders en el payload
    if payload and "rol_id" in payload:
        payload["rol_id"] = str(test_rol_usuario_regular.id)
        payload["nombre_usuario"] = f"testuser_{uuid4().hex[:6]}"
        payload["email"] = f"test_{uuid4().hex[:6]}@example.com"

    # Realizar la petición HTTP
    response = await client.request(
        method=http_method,
        url=f"{settings.API_V1_STR}{endpoint}",
        headers=headers,
        json=payload if payload else None
    )
    
    # Verificar el código de estado
    assert response.status_code == expected_status, (
        f"Fallo en el test de permiso para ROL: {rol_fixture}, "
        f"ENDPOINT: {http_method} {endpoint}, "
        f"PAYLOAD: {payload}. "
        f"Respuesta recibida: {response.status_code} {response.text}"
    )
