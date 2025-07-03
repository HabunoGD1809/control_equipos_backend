import pytest
from httpx import AsyncClient
from fastapi import status
from uuid import uuid4
from sqlalchemy.orm import Session
from typing import Callable

from app.core.config import settings
from app.models import (
    Usuario, Rol, Proveedor, Equipo, TipoDocumento, ReservaEquipo, EstadoEquipo,
)

# Marcar todos los tests como asíncronos
pytestmark = pytest.mark.asyncio


# --- Fixture de conveniencia ---
@pytest.fixture(scope="function")
async def all_auth_tokens(
    auth_token_usuario_regular: str,
    auth_token_tecnico: str,
    auth_token_supervisor: str,
    auth_token_auditor: str,
    auth_token_admin: str
) -> dict[str, str]:
    """Agrupa todos los tokens para un acceso más fácil en las pruebas parametrizadas."""
    return {
        "regular": auth_token_usuario_regular,
        "tecnico": auth_token_tecnico,
        "supervisor": auth_token_supervisor,
        "auditor": auth_token_auditor,
        "admin": auth_token_admin,
    }

# --- DEFINICIÓN EXHAUSTIVA DE PRUEBAS DE PERMISOS ---
# Formato: (descripción, método, endpoint, rol, status_esperado, payload_factory)

def generar_numero_serie_valido():
    """Genera un número de serie que cumple con el formato XXX-YYYY-ZZZZ."""
    return f"SER-{uuid4().hex[:4].upper()}-{uuid4().hex[:4].upper()}"

# Módulo: Equipos
equipos_permissions = [
    ("Admin puede crear equipo", "POST", "/equipos/", "admin", status.HTTP_201_CREATED, lambda estado_id: {"nombre": "Equipo-Test-Admin", "numero_serie": generar_numero_serie_valido(), "estado_id": str(estado_id)}),
    ("Supervisor puede crear equipo", "POST", "/equipos/", "supervisor", status.HTTP_201_CREATED, lambda estado_id: {"nombre": "Equipo-Test-Super", "numero_serie": generar_numero_serie_valido(), "estado_id": str(estado_id)}),
    ("Técnico NO puede crear equipo", "POST", "/equipos/", "tecnico", status.HTTP_403_FORBIDDEN, lambda estado_id: {"nombre": "Equipo-Test-Tecnico", "numero_serie": generar_numero_serie_valido(), "estado_id": str(estado_id)}),
    ("Admin puede borrar equipo", "DELETE", "/equipos/{id}", "admin", status.HTTP_200_OK, None),
    ("Supervisor puede borrar equipo", "DELETE", "/equipos/{id}", "supervisor", status.HTTP_200_OK, None),
    ("Técnico NO puede borrar equipo", "DELETE", "/equipos/{id}", "tecnico", status.HTTP_403_FORBIDDEN, None),
    ("Usuario Regular puede ver equipos", "GET", "/equipos/", "regular", status.HTTP_200_OK, None),
]

# Módulo: Proveedores
proveedores_permissions = [
    ("Admin puede crear proveedor", "POST", "/proveedores/", "admin", status.HTTP_201_CREATED, lambda: {"nombre": f"Prov-{uuid4().hex[:4]}"}),
    ("Supervisor puede crear proveedor", "POST", "/proveedores/", "supervisor", status.HTTP_201_CREATED, lambda: {"nombre": f"Prov-{uuid4().hex[:4]}"}),
    ("Técnico NO puede crear proveedor", "POST", "/proveedores/", "tecnico", status.HTTP_403_FORBIDDEN, lambda: {"nombre": f"Prov-{uuid4().hex[:4]}"}),
    ("Usuario Regular NO puede crear proveedor", "POST", "/proveedores/", "regular", status.HTTP_403_FORBIDDEN, lambda: {"nombre": f"Prov-{uuid4().hex[:4]}"}),
    ("Admin puede borrar proveedor", "DELETE", "/proveedores/{id}", "admin", status.HTTP_200_OK, None),
    ("Supervisor puede borrar proveedor", "DELETE", "/proveedores/{id}", "supervisor", status.HTTP_200_OK, None),
]

# Módulo: Catálogos (ej. Tipos de Documento)
catalogos_permissions = [
    ("Admin puede crear tipo de documento", "POST", "/catalogos/tipos-documento/", "admin", status.HTTP_201_CREATED, lambda: {"nombre": f"Doc-{uuid4().hex[:4]}"}),
    ("Supervisor puede crear tipo de doc", "POST", "/catalogos/tipos-documento/", "supervisor", status.HTTP_201_CREATED, lambda: {"nombre": f"Doc-{uuid4().hex[:4]}"}),
    ("Técnico NO puede crear tipo de doc", "POST", "/catalogos/tipos-documento/", "tecnico", status.HTTP_403_FORBIDDEN, lambda: {"nombre": f"Doc-{uuid4().hex[:4]}"}),
    ("Admin puede borrar tipo de doc", "DELETE", "/catalogos/tipos-documento/{id}", "admin", status.HTTP_200_OK, None),
    ("Supervisor PUEDE crear estado de equipo", "POST", "/catalogos/estados-equipo/", "supervisor", status.HTTP_201_CREATED, lambda: {"nombre": f"Estado-{uuid4().hex[:4]}", "color_hex": "#FFFFFF"}),
    ("Admin puede crear estado de equipo", "POST", "/catalogos/estados-equipo/", "admin", status.HTTP_201_CREATED, lambda: {"nombre": f"Estado-{uuid4().hex[:4]}", "color_hex": "#FFFFFF"}),
]

# Módulo: Gestión de Usuarios y Roles
usuarios_roles_permissions = [
    ("Admin puede crear un rol", "POST", "/gestion/roles/", "admin", status.HTTP_201_CREATED, lambda: {"nombre": f"Rol-Test-{uuid4().hex[:4]}", "permisos_nombres": ["ver_dashboard"]}),
    ("Supervisor NO puede crear un rol", "POST", "/gestion/roles/", "supervisor", status.HTTP_403_FORBIDDEN, lambda: {"nombre": f"Rol-Test-{uuid4().hex[:4]}", "permisos_nombres": ["ver_dashboard"]}),
    ("Admin puede borrar un rol", "DELETE", "/gestion/roles/{id}", "admin", status.HTTP_200_OK, None),
    ("Supervisor puede crear usuario", "POST", "/usuarios/", "supervisor", status.HTTP_201_CREATED, lambda rol_id: {"nombre_usuario": f"u-{uuid4().hex[:6]}", "password": "ValidPassword123!", "rol_id": str(rol_id)}),
    ("Técnico NO puede crear usuario", "POST", "/usuarios/", "tecnico", status.HTTP_403_FORBIDDEN, lambda rol_id: {"nombre_usuario": f"u-{uuid4().hex[:6]}", "password": "ValidPassword123!", "rol_id": str(rol_id)}),
]

# Módulo: Auditoría y Permisos de Solo Lectura
auditoria_permissions = [
    ("Auditor PUEDE ver logs de auditoría", "GET", "/auditoria/", "auditor", status.HTTP_200_OK, None),
    ("Usuario Regular NO puede ver logs de auditoría", "GET", "/auditoria/", "regular", status.HTTP_403_FORBIDDEN, None),
    ("Auditor NO PUEDE crear equipo", "POST", "/equipos/", "auditor", status.HTTP_403_FORBIDDEN, lambda estado_id: {"nombre": "Audit-Test", "numero_serie": generar_numero_serie_valido(), "estado_id": str(estado_id)}),
    ("Auditor NO PUEDE cancelar una reserva", "POST", "/reservas/{id}/cancelar", "auditor", status.HTTP_403_FORBIDDEN, None),
    ("Auditor NO PUEDE ver la lista de usuarios", "GET", "/usuarios/", "auditor", status.HTTP_403_FORBIDDEN, None),
]

# Unimos todas las listas de pruebas en una sola para el test parametrizado
all_permission_tests = (
    equipos_permissions +
    proveedores_permissions +
    catalogos_permissions +
    usuarios_roles_permissions +
    auditoria_permissions
)

@pytest.mark.parametrize(
    "test_desc, http_method, endpoint_template, rol, expected_status, payload_factory",
    all_permission_tests
)
async def test_permission_matrix_expanded(
    client: AsyncClient, all_auth_tokens: dict,
    test_desc: str, http_method: str, endpoint_template: str, rol: str, expected_status: int, payload_factory: Callable | None,
    # Fixtures para obtener IDs de objetos a manipular
    test_proveedor_para_borrar: Proveedor,
    test_equipo_para_borrar: Equipo,
    test_tipo_doc_para_borrar: TipoDocumento,
    test_rol_para_borrar: Rol,
    test_reserva_para_cancelar: ReservaEquipo,
    test_rol_usuario_regular: Rol,
    test_estado_disponible: EstadoEquipo
):
    """
    Test parametrizado y modular que verifica la matriz de permisos para diferentes roles y endpoints.
    """
    auth_token = all_auth_tokens[rol]
    headers = {"Authorization": f"Bearer {auth_token}"}

    # Prepara el endpoint con el ID del objeto correspondiente
    endpoint = endpoint_template
    if "{id}" in endpoint_template:
        if "/proveedores/" in endpoint_template:
            endpoint = endpoint_template.format(id=test_proveedor_para_borrar.id)
        elif "/equipos/" in endpoint_template:
            endpoint = endpoint_template.format(id=test_equipo_para_borrar.id)
        elif "/tipos-documento/" in endpoint_template:
            endpoint = endpoint_template.format(id=test_tipo_doc_para_borrar.id)
        elif "/gestion/roles/" in endpoint_template:
            endpoint = endpoint_template.format(id=test_rol_para_borrar.id)
        elif "/reservas/" in endpoint_template:
            endpoint = endpoint_template.format(id=test_reserva_para_cancelar.id)
    
    # Prepara el payload si es una operación que lo requiere
    payload = None
    if payload_factory:
        # Pasa dependencias a la lambda si las necesita
        if endpoint_template == "/equipos/" and http_method == "POST":
            payload = payload_factory(test_estado_disponible.id)
        elif "usuario" in endpoint_template and http_method == "POST":
            payload = payload_factory(test_rol_usuario_regular.id)
        else:
            payload = payload_factory()

    # Realiza la petición
    response = await client.request(method=http_method, url=f"{settings.API_V1_STR}{endpoint}", headers=headers, json=payload)
    
    # Realiza la aserción con un mensaje de error detallado
    assert response.status_code == expected_status, \
        (f"FALLO DE PERMISO para ROL '{rol.upper()}' al intentar '{test_desc}'.\n"
         f"--> Endpoint: {http_method} {endpoint}\n"
         f"--> Payload: {payload}\n"
         f"--> ESPERADO: {expected_status}, RECIBIDO: {response.status_code} - {response.text}")
