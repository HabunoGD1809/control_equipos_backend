import pytest
from httpx import AsyncClient
from uuid import uuid4, UUID
from datetime import datetime, timedelta, timezone
from fastapi import status
from fastapi.encoders import jsonable_encoder

from app.core.config import settings
from app.models.equipo import Equipo
from app.models.estado_equipo import EstadoEquipo
from app.models.movimiento import Movimiento
from app.schemas.enums import TipoMovimientoEquipoEnum
from app.schemas.movimiento import MovimientoCreate, MovimientoUpdate
from app.models.usuario import Usuario

from sqlalchemy.orm import Session
from decimal import Decimal

pytestmark = pytest.mark.asyncio

@pytest.fixture(scope="function")
async def equipo_para_movimiento(
    db: Session, test_estado_disponible: EstadoEquipo
) -> Equipo:
    from tests.api.v1.test_equipos import generate_valid_serie
    serie = generate_valid_serie("MOV")
    equipo = Equipo(
        nombre=f"Equipo Mov {serie}", 
        numero_serie=serie,
        estado_id=test_estado_disponible.id,
        ubicacion_actual="Almacén IT",
        marca="Test",
        modelo="Mov",
        codigo_interno=f"MOV-{serie}",
        valor_adquisicion=Decimal("0.00"),
        centro_costo="Test"
    )
    db.add(equipo)
    db.flush()
    db.refresh(equipo)
    return equipo

async def test_create_movimiento_asignacion_success(
    client: AsyncClient, auth_token_supervisor: str, equipo_para_movimiento: Equipo
):
    headers = {"Authorization": f"Bearer {auth_token_supervisor}"}
    movimiento_schema = MovimientoCreate(
        equipo_id=equipo_para_movimiento.id,
        tipo_movimiento=TipoMovimientoEquipoEnum.ASIGNACION_INTERNA,
        origen="Almacén IT",
        destino="Usuario Test Destino",
        proposito="Asignación para proyecto X",
        fecha_prevista_retorno=None,
        recibido_por="John Doe",
        observaciones="Entrega de equipo nuevo"
    )
    data = jsonable_encoder(movimiento_schema)
    response = await client.post(f"{settings.API_V1_STR}/movimientos/", headers=headers, json=data)

    assert response.status_code == status.HTTP_201_CREATED, f"Detalle error: {response.text}"
    created_movimiento = response.json()
    assert created_movimiento["equipo_id"] == str(equipo_para_movimiento.id)
    assert created_movimiento["tipo_movimiento"] == "Asignacion Interna"
    assert created_movimiento["destino"] == "Usuario Test Destino"
    assert "id" in created_movimiento
    assert created_movimiento["estado"] == "Completado"

    get_equipo_resp = await client.get(f"{settings.API_V1_STR}/equipos/{equipo_para_movimiento.id}", headers=headers)
    assert get_equipo_resp.status_code == status.HTTP_200_OK
    equipo_actualizado = get_equipo_resp.json()
    assert equipo_actualizado["ubicacion_actual"] == "Usuario Test Destino"
    assert equipo_actualizado.get("estado", {}).get("nombre") == "En Uso"

async def test_create_movimiento_salida_temporal_success(
    client: AsyncClient, auth_token_supervisor: str, equipo_para_movimiento: Equipo
):
    headers = {"Authorization": f"Bearer {auth_token_supervisor}"}
    fecha_retorno_prevista = datetime.now(timezone.utc) + timedelta(days=7)
    movimiento_schema = MovimientoCreate(
        equipo_id=equipo_para_movimiento.id,
        tipo_movimiento=TipoMovimientoEquipoEnum.SALIDA_TEMPORAL,
        origen="Almacén IT",
        destino="Cliente Externo Y",
        proposito="Préstamo para demo",
        fecha_prevista_retorno=fecha_retorno_prevista,
        recibido_por="Jane Smith",
        observaciones="Demo en sitio del cliente"
    )
    data = jsonable_encoder(movimiento_schema)
    response = await client.post(f"{settings.API_V1_STR}/movimientos/", headers=headers, json=data)

    assert response.status_code == status.HTTP_201_CREATED, f"Detalle error: {response.text}"
    created_movimiento = response.json()
    assert created_movimiento["tipo_movimiento"] == "Salida Temporal"
    assert created_movimiento["destino"] == "Cliente Externo Y"
    assert created_movimiento["fecha_prevista_retorno"] is not None

    get_equipo_resp = await client.get(f"{settings.API_V1_STR}/equipos/{equipo_para_movimiento.id}", headers=headers)
    assert get_equipo_resp.status_code == status.HTTP_200_OK
    equipo_actualizado = get_equipo_resp.json()
    assert equipo_actualizado["ubicacion_actual"] == "Cliente Externo Y"
    assert equipo_actualizado.get("estado", {}).get("nombre") == "Prestado"

async def test_create_movimiento_no_permission(
    client: AsyncClient, auth_token_usuario_regular: str, equipo_para_movimiento: Equipo
):
    headers = {"Authorization": f"Bearer {auth_token_usuario_regular}"}
    movimiento_schema = MovimientoCreate(
        equipo_id=equipo_para_movimiento.id, tipo_movimiento=TipoMovimientoEquipoEnum.ASIGNACION_INTERNA,
        origen="Origen", destino="Destino", proposito="Test",
        fecha_prevista_retorno=None, recibido_por=None, observaciones=None
    )
    data = jsonable_encoder(movimiento_schema)
    response = await client.post(f"{settings.API_V1_STR}/movimientos/", headers=headers, json=data)
    assert response.status_code == status.HTTP_403_FORBIDDEN

async def test_create_movimiento_equipo_not_found(
    client: AsyncClient, auth_token_supervisor: str
):
    headers = {"Authorization": f"Bearer {auth_token_supervisor}"}
    invalid_equipo_id = uuid4()
    movimiento_schema = MovimientoCreate(
        equipo_id=invalid_equipo_id, tipo_movimiento=TipoMovimientoEquipoEnum.ASIGNACION_INTERNA,
        origen="Origen", destino="Destino", proposito="Test",
        fecha_prevista_retorno=None, recibido_por=None, observaciones=None
    )
    data = jsonable_encoder(movimiento_schema)
    response = await client.post(f"{settings.API_V1_STR}/movimientos/", headers=headers, json=data)
    assert response.status_code == status.HTTP_404_NOT_FOUND, f"Detalle error: {response.text}"
    assert "equipo no encontrado" in response.json()["detail"].lower()

async def test_create_movimiento_missing_data_for_type(
    client: AsyncClient, auth_token_supervisor: str, equipo_para_movimiento: Equipo
):
    headers = {"Authorization": f"Bearer {auth_token_supervisor}"}
    movimiento_schema = MovimientoCreate(
        equipo_id=equipo_para_movimiento.id,
        tipo_movimiento=TipoMovimientoEquipoEnum.SALIDA_TEMPORAL,
        origen=None, destino=None, proposito=None, fecha_prevista_retorno=None,
        recibido_por=None, observaciones=None
    )
    data = jsonable_encoder(movimiento_schema)
    response = await client.post(f"{settings.API_V1_STR}/movimientos/", headers=headers, json=data)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, f"Detalle error: {response.text}"
    assert "obligatoria" in response.json()["detail"].lower()

async def test_read_movimientos_success(
    client: AsyncClient, auth_token_supervisor: str, equipo_para_movimiento: Equipo
):
    headers = {"Authorization": f"Bearer {auth_token_supervisor}"}
    movimiento_schema = MovimientoCreate(
        equipo_id=equipo_para_movimiento.id, tipo_movimiento=TipoMovimientoEquipoEnum.ASIGNACION_INTERNA,
        origen="Origen List", destino="Destino List", proposito="Test",
        fecha_prevista_retorno=None, recibido_por=None, observaciones=None
    )
    data = jsonable_encoder(movimiento_schema)
    create_response = await client.post(f"{settings.API_V1_STR}/movimientos/", headers=headers, json=data)
    assert create_response.status_code == status.HTTP_201_CREATED, f"Fallo al crear movimiento previo: {create_response.text}"

    response = await client.get(f"{settings.API_V1_STR}/movimientos/", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    movimientos = response.json()
    assert isinstance(movimientos, list)
    assert len(movimientos) > 0

async def test_read_movimientos_filter_by_equipo(
    client: AsyncClient, auth_token_supervisor: str, equipo_para_movimiento: Equipo
):
    headers = {"Authorization": f"Bearer {auth_token_supervisor}"}
    movimiento_schema = MovimientoCreate(
        equipo_id=equipo_para_movimiento.id, tipo_movimiento=TipoMovimientoEquipoEnum.ENTRADA,
        origen="Proveedor X", destino="Almacén IT", proposito="Compra",
        fecha_prevista_retorno=None, recibido_por=None, observaciones=None
    )
    data = jsonable_encoder(movimiento_schema)
    create_response = await client.post(f"{settings.API_V1_STR}/movimientos/", headers=headers, json=data)
    assert create_response.status_code == status.HTTP_201_CREATED, f"Fallo al crear movimiento previo: {create_response.text}"
    created_movimiento_id = create_response.json().get("id")
    assert created_movimiento_id is not None, "La respuesta de creación no devolvió un ID."

    response = await client.get(f"{settings.API_V1_STR}/movimientos/", headers=headers, params={"equipo_id": str(equipo_para_movimiento.id)})
    assert response.status_code == status.HTTP_200_OK
    movimientos = response.json()
    assert isinstance(movimientos, list)
    assert len(movimientos) > 0
    assert all(m["equipo_id"] == str(equipo_para_movimiento.id) for m in movimientos)
    assert any(m["id"] == created_movimiento_id for m in movimientos)

async def test_read_movimiento_by_id_success(
    client: AsyncClient, auth_token_supervisor: str, equipo_para_movimiento: Equipo
):
    headers = {"Authorization": f"Bearer {auth_token_supervisor}"}
    movimiento_schema = MovimientoCreate(
        equipo_id=equipo_para_movimiento.id, tipo_movimiento=TipoMovimientoEquipoEnum.ASIGNACION_INTERNA,
        origen="Origen ID", destino="Destino ID", proposito="Test",
        fecha_prevista_retorno=None, recibido_por=None, observaciones=None
    )
    data = jsonable_encoder(movimiento_schema)
    create_response = await client.post(f"{settings.API_V1_STR}/movimientos/", headers=headers, json=data)
    assert create_response.status_code == status.HTTP_201_CREATED, f"Fallo al crear movimiento previo: {create_response.text}"
    movimiento_id = create_response.json().get("id")
    assert movimiento_id is not None, "La respuesta de creación no devolvió un ID."

    response = await client.get(f"{settings.API_V1_STR}/movimientos/{movimiento_id}", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    mov_data = response.json()
    assert mov_data["id"] == movimiento_id
    assert mov_data["tipo_movimiento"] == "Asignacion Interna"

async def test_read_movimiento_by_id_not_found(
    client: AsyncClient, auth_token_supervisor: str
):
    headers = {"Authorization": f"Bearer {auth_token_supervisor}"}
    non_existent_id = uuid4()
    response = await client.get(f"{settings.API_V1_STR}/movimientos/{non_existent_id}", headers=headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND

async def test_update_movimiento_observaciones_success(
    client: AsyncClient, auth_token_supervisor: str, equipo_para_movimiento: Equipo
):
    headers = {"Authorization": f"Bearer {auth_token_supervisor}"}
    create_schema = MovimientoCreate(
        equipo_id=equipo_para_movimiento.id, tipo_movimiento=TipoMovimientoEquipoEnum.ASIGNACION_INTERNA,
        origen="O", destino="D", observaciones="Obs Original", proposito="Test",
        fecha_prevista_retorno=None, recibido_por=None
    )
    create_data = jsonable_encoder(create_schema)
    create_response = await client.post(f"{settings.API_V1_STR}/movimientos/", headers=headers, json=create_data)
    assert create_response.status_code == status.HTTP_201_CREATED, f"Fallo al crear movimiento previo: {create_response.text}"
    movimiento_id = create_response.json().get("id")
    assert movimiento_id is not None, "La respuesta de creación no devolvió un ID."

    update_schema = MovimientoUpdate(observaciones="Observaciones actualizadas por test", recibido_por="Updated Test")
    update_data = jsonable_encoder(update_schema.model_dump(exclude_unset=True))
    
    update_response = await client.put(f"{settings.API_V1_STR}/movimientos/{movimiento_id}", headers=headers, json=update_data)
    
    assert update_response.status_code == status.HTTP_200_OK, f"Detalle error: {update_response.text}"
    
    updated_mov = update_response.json()
    assert updated_mov["id"] == movimiento_id
    assert updated_mov["observaciones"] == "Observaciones actualizadas por test"
    assert updated_mov["recibido_por"] == "Updated Test"

async def test_cancel_movimiento_fail_on_completed(
    client: AsyncClient, auth_token_supervisor: str, equipo_para_movimiento: Equipo
):
    """Verifica que no se puede cancelar un movimiento ya completado."""
    headers = {"Authorization": f"Bearer {auth_token_supervisor}"}
    create_schema = MovimientoCreate(
         equipo_id=equipo_para_movimiento.id, tipo_movimiento=TipoMovimientoEquipoEnum.ASIGNACION_INTERNA,
         origen="O", destino="D", proposito="Test para Cancelar (fallo)",
         fecha_prevista_retorno=None, recibido_por=None, observaciones=None
    )
    create_data = jsonable_encoder(create_schema)
    create_response = await client.post(f"{settings.API_V1_STR}/movimientos/", headers=headers, json=create_data)
    assert create_response.status_code == status.HTTP_201_CREATED, f"Fallo al crear movimiento previo: {create_response.text}"
    
    mov_response = create_response.json()
    movimiento_id = mov_response.get("id")
    original_estado = mov_response.get("estado", "Desconocido")
    
    assert original_estado == "Completado"

    cancel_response = await client.post(f"{settings.API_V1_STR}/movimientos/{movimiento_id}/cancelar", headers=headers)
    assert cancel_response.status_code == status.HTTP_409_CONFLICT, f"Detalle error: {cancel_response.text}"
    assert "no se puede cancelar un movimiento en estado 'completado'" in cancel_response.json()["detail"].lower()


async def test_cancel_movimiento_success_on_cancelable_state(
    client: AsyncClient, auth_token_supervisor: str, equipo_para_movimiento: Equipo, db: Session
):
    """Verifica que un movimiento en estado cancelable puede ser cancelado."""
    headers = {"Authorization": f"Bearer {auth_token_supervisor}"}
    
    fecha_retorno = datetime.now(timezone.utc) + timedelta(days=5)

    mov_pendiente = Movimiento(
        equipo_id=equipo_para_movimiento.id,
        tipo_movimiento=TipoMovimientoEquipoEnum.SALIDA_TEMPORAL.value,
        estado="Pendiente",
        origen="Almacén",
        destino="Externo",
        proposito="Prueba de cancelación exitosa",
        fecha_prevista_retorno=fecha_retorno
    )
    db.add(mov_pendiente)
    db.commit()
    db.refresh(mov_pendiente)
    movimiento_id = mov_pendiente.id
    
    cancel_response = await client.post(f"{settings.API_V1_STR}/movimientos/{movimiento_id}/cancelar", headers=headers)
    assert cancel_response.status_code == status.HTTP_200_OK, f"Detalle error: {cancel_response.text}"
    
    cancelled_mov = cancel_response.json()
    assert cancelled_mov["id"] == str(movimiento_id)
    assert cancelled_mov["estado"] == "Cancelado"
    assert "Cancelado por" in cancelled_mov["observaciones"]
