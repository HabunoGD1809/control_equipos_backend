import pytest
from httpx import AsyncClient
from uuid import uuid4, UUID as PyUUID
from fastapi.encoders import jsonable_encoder
from decimal import Decimal

from app.core.config import settings
from app.models.equipo import Equipo
from app.models.estado_equipo import EstadoEquipo
from app.schemas.equipo import EquipoCreate
from fastapi import status
from datetime import date

pytestmark = pytest.mark.asyncio

# --- Función auxiliar para generar series válidas ---
def generate_valid_serie(prefix: str) -> str:
    part1 = prefix.upper()
    part2 = uuid4().hex[:4].upper()
    part3 = uuid4().hex[:4].upper()
    return f"{part1}-{part2}-{part3}"

# --- Tests para Equipos ---

async def test_create_equipo_success(
    client: AsyncClient, auth_token_supervisor: str, test_estado_disponible: EstadoEquipo
):
    headers = {"Authorization": f"Bearer {auth_token_supervisor}"}
    numero_serie_valido = generate_valid_serie("CREATE")
    equipo_data = {
        "nombre": "Laptop Test Create Success",
        "marca": "TestBrand",
        "modelo": "TestModelX",
        "numero_serie": numero_serie_valido,
        "codigo_interno": f"CI-{numero_serie_valido}",
        "estado_id": str(test_estado_disponible.id),
        "descripcion": "Laptop creada en test",
        "fecha_adquisicion": date(2024, 1, 15).isoformat(),
        "valor_adquisicion": "1200.50"
    }
    response = await client.post(f"{settings.API_V1_STR}/equipos/", headers=headers, json=equipo_data)
    assert response.status_code == status.HTTP_201_CREATED, f"Detalle error: {response.text}"
    created_equipo = response.json()
    assert created_equipo["nombre"] == equipo_data["nombre"]
    assert created_equipo["numero_serie"] == equipo_data["numero_serie"]
    assert "id" in created_equipo

async def test_create_equipo_invalid_serie_format(
    client: AsyncClient, auth_token_supervisor: str, test_estado_disponible: EstadoEquipo
):
    """Prueba crear equipo con formato de número de serie incorrecto."""
    headers = {"Authorization": f"Bearer {auth_token_supervisor}"}
    equipo_data_invalid_serie = {
        "nombre": "Laptop Serie Inválida",
        "numero_serie": "SERIE_INVALIDA_SIN_GUIONES",
        "codigo_interno": "CI-INVALID",
        "estado_id": str(test_estado_disponible.id),
        "marca": "TestBrand",
        "modelo": "TestModelY",
        "valor_adquisicion": "0.00",
        "centro_costo": "Test"
    }
    response = await client.post(f"{settings.API_V1_STR}/equipos/", headers=headers, json=equipo_data_invalid_serie)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, f"Detalle error: {response.text}"
    assert "no es válido" in response.text


# --- Tests para Componentes ---

async def test_add_componente_success(
    client: AsyncClient, auth_token_supervisor: str,
    test_equipo_principal: Equipo, test_componente_ram: Equipo
):
    """Prueba añadir un componente válido a un equipo."""
    headers = {"Authorization": f"Bearer {auth_token_supervisor}"}
    equipo_padre_id = test_equipo_principal.id
    componente_a_anadir_id = test_componente_ram.id

    componente_payload = {
        "equipo_componente_id": str(componente_a_anadir_id),
        "cantidad": 2,
        # CORREGIDO: Se cambia "Instalado en" por un valor válido de la constraint CHECK
        "tipo_relacion": "componente",
        "notas": "RAM 2x añadida en test de éxito"
    }
    response = await client.post(
        f"{settings.API_V1_STR}/equipos/{equipo_padre_id}/componentes",
        headers=headers,
        json=componente_payload
    )
    assert response.status_code == status.HTTP_201_CREATED, f"Detalle: {response.text}"
    relacion_creada = response.json()
    assert relacion_creada["equipo_padre_id"] == str(equipo_padre_id)
    assert relacion_creada["equipo_componente_id"] == str(componente_a_anadir_id)
    assert relacion_creada["tipo_relacion"] == "componente"

async def test_add_componente_ciclico(
    client: AsyncClient, auth_token_supervisor: str,
    test_equipo_principal: Equipo
):
    """Prueba evitar añadir un equipo como componente de sí mismo."""
    headers = {"Authorization": f"Bearer {auth_token_supervisor}"}
    equipo_id_padre_y_componente = test_equipo_principal.id

    componente_payload = {
        "equipo_componente_id": str(equipo_id_padre_y_componente),
        "cantidad": 1,
        "tipo_relacion": "componente"
    }
    response = await client.post(
        f"{settings.API_V1_STR}/equipos/{equipo_id_padre_y_componente}/componentes",
        headers=headers,
        json=componente_payload
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST, f"Detalle: {response.text}"
    assert "no puede ser componente de sí mismo" in response.json()["detail"].lower()


# --- Otros Tests de Equipos (CRUD, permisos, etc.) ---

async def test_create_equipo_no_permission(
    client: AsyncClient, auth_token_usuario_regular: str, test_estado_disponible: EstadoEquipo
):
    # CORREGIDO: Se usa auth_token_usuario_regular
    headers = {"Authorization": f"Bearer {auth_token_usuario_regular}"}
    serie = generate_valid_serie("NOPERM")
    equipo_schema = EquipoCreate(
        nombre=f"Equipo Test NoPerm {serie}", 
        numero_serie=serie, 
        codigo_interno=f"CI-{serie}",
        estado_id=test_estado_disponible.id,
        valor_adquisicion=Decimal("0.00"),
        centro_costo="Test",
        marca="Test",
        modelo="Test"
    )
    data = jsonable_encoder(equipo_schema)
    response = await client.post(f"{settings.API_V1_STR}/equipos/", headers=headers, json=data)
    assert response.status_code == status.HTTP_403_FORBIDDEN, f"Detalle: {response.text}"

async def test_create_equipo_duplicate_serie(
    client: AsyncClient, auth_token_supervisor: str,
    test_estado_disponible: EstadoEquipo
):
    headers = {"Authorization": f"Bearer {auth_token_supervisor}"}
    serie_duplicada = generate_valid_serie("DUPSERIE")

    equipo_schema1 = EquipoCreate(
        nombre=f"Equipo A {serie_duplicada}", 
        numero_serie=serie_duplicada, 
        codigo_interno=f"CI-A-{serie_duplicada}",
        estado_id=test_estado_disponible.id,
        valor_adquisicion=Decimal("1.00"),
        centro_costo="Test",
        marca="Test",
        modelo="Test"
    )
    response1 = await client.post(f"{settings.API_V1_STR}/equipos/", headers=headers, json=jsonable_encoder(equipo_schema1))
    assert response1.status_code == status.HTTP_201_CREATED, f"Error al crear primer equipo: {response1.text}"

    equipo_schema2 = EquipoCreate(
        nombre=f"Equipo B {serie_duplicada}", 
        numero_serie=serie_duplicada, 
        codigo_interno=f"CI-B-{serie_duplicada}",
        estado_id=test_estado_disponible.id,
        valor_adquisicion=Decimal("1.00"),
        centro_costo="Test",
        marca="Test",
        modelo="Test"
    )
    response2 = await client.post(f"{settings.API_V1_STR}/equipos/", headers=headers, json=jsonable_encoder(equipo_schema2))

    assert response2.status_code == status.HTTP_409_CONFLICT, f"Detalle: {response2.text}"
    assert "número de serie ya registrado" in response2.json()["detail"].lower()


async def test_read_equipos(client: AsyncClient, auth_token_usuario_regular: str):
    # CORREGIDO: Se usa auth_token_usuario_regular
    headers = {"Authorization": f"Bearer {auth_token_usuario_regular}"}
    response = await client.get(f"{settings.API_V1_STR}/equipos/", headers=headers)
    assert response.status_code == status.HTTP_200_OK, f"Detalle: {response.text}"
    assert isinstance(response.json(), list)

async def test_read_equipo_by_id(
    client: AsyncClient, auth_token_supervisor: str, test_estado_disponible: EstadoEquipo
):
    headers = {"Authorization": f"Bearer {auth_token_supervisor}"}
    serie = generate_valid_serie("READID")
    create_schema = EquipoCreate(
        nombre=f"Equipo ReadByID {serie}", 
        numero_serie=serie, 
        codigo_interno=f"CI-{serie}",
        estado_id=test_estado_disponible.id,
        valor_adquisicion=Decimal("1.00"),
        centro_costo="Test",
        marca="Test",
        modelo="Test"
    )
    create_response = await client.post(f"{settings.API_V1_STR}/equipos/", headers=headers, json=jsonable_encoder(create_schema))
    assert create_response.status_code == status.HTTP_201_CREATED
    equipo_id = create_response.json()["id"]

    read_response = await client.get(f"{settings.API_V1_STR}/equipos/{equipo_id}", headers=headers)
    assert read_response.status_code == status.HTTP_200_OK
    read_equipo = read_response.json()
    assert read_equipo["id"] == equipo_id
    assert read_equipo["numero_serie"] == serie

async def test_update_equipo(
    client: AsyncClient, auth_token_supervisor: str,
    test_estado_disponible: EstadoEquipo
):
    headers = {"Authorization": f"Bearer {auth_token_supervisor}"}
    serie = generate_valid_serie("UPD")
    create_schema = EquipoCreate(
        nombre=f"Original {serie}", 
        numero_serie=serie, 
        codigo_interno=f"CI-{serie}",
        estado_id=test_estado_disponible.id, 
        ubicacion_actual="Almacen A",
        valor_adquisicion=Decimal("1.00"),
        centro_costo="Test",
        marca="Test",
        modelo="Test"
    )
    create_response = await client.post(f"{settings.API_V1_STR}/equipos/", headers=headers, json=jsonable_encoder(create_schema))
    assert create_response.status_code == status.HTTP_201_CREATED
    equipo_id = create_response.json()["id"]

    update_payload = {"nombre": "Equipo Super Actualizado", "ubicacion_actual": "Oficina XYZ", "notas": "Actualizado por test"}
    update_response = await client.put(f"{settings.API_V1_STR}/equipos/{equipo_id}", headers=headers, json=update_payload)
    assert update_response.status_code == status.HTTP_200_OK, f"Detalle: {update_response.text}"
    updated_equipo = update_response.json()
    assert updated_equipo["id"] == equipo_id
    assert updated_equipo["nombre"] == update_payload["nombre"]

async def test_delete_equipo(
     client: AsyncClient, auth_token_admin: str,
     test_estado_disponible: EstadoEquipo
):
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    serie = generate_valid_serie("DEL")
    create_schema = EquipoCreate(
        nombre=f"Equipo Para Borrar {serie}", 
        numero_serie=serie, 
        codigo_interno=f"CI-{serie}",
        estado_id=test_estado_disponible.id,
        valor_adquisicion=Decimal("1.00"),
        centro_costo="Test",
        marca="Test",
        modelo="Test"
    )
    create_response = await client.post(f"{settings.API_V1_STR}/equipos/", headers=headers, json=jsonable_encoder(create_schema))
    assert create_response.status_code == status.HTTP_201_CREATED
    equipo_id = create_response.json()["id"]

    delete_response = await client.delete(f"{settings.API_V1_STR}/equipos/{equipo_id}", headers=headers)
    assert delete_response.status_code == status.HTTP_200_OK
    assert "eliminado correctamente" in delete_response.json().get("msg", "")

    get_response = await client.get(f"{settings.API_V1_STR}/equipos/{equipo_id}", headers=headers)
    assert get_response.status_code == status.HTTP_404_NOT_FOUND

