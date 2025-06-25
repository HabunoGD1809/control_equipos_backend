import pytest
from httpx import AsyncClient
from uuid import uuid4, UUID
from datetime import datetime, timedelta, timezone
from fastapi import status
from fastapi.encoders import jsonable_encoder

from app.core.config import settings
from app.models.equipo import Equipo
from app.models.reserva_equipo import ReservaEquipo
from app.schemas.reserva_equipo import ReservaEquipoCreate, ReservaEquipoUpdate, ReservaEquipoUpdateEstado
from app.schemas.enums import EstadoReservaEnum

from sqlalchemy.orm import Session
from app.models.usuario import Usuario

pytestmark = pytest.mark.asyncio

async def test_create_reserva_success(
    client: AsyncClient, auth_token_user: str,
    test_equipo_reservable: Equipo
):
    headers = {"Authorization": f"Bearer {auth_token_user}"}
    
    start_time = datetime.now(timezone.utc) + timedelta(days=1, hours=2)
    end_time = start_time + timedelta(hours=2)

    reserva_schema = ReservaEquipoCreate(
        equipo_id=test_equipo_reservable.id,
        fecha_hora_inicio=start_time,
        fecha_hora_fin=end_time,
        proposito="Reunión de planificación",
        notas_solicitante="Necesita proyector"
    )
    data = jsonable_encoder(reserva_schema)
    response = await client.post(f"{settings.API_V1_STR}/reservas/", headers=headers, json=data)

    assert response.status_code == status.HTTP_201_CREATED, f"Detalle error: {response.text}"
    created_reserva = response.json()
    assert created_reserva["equipo_id"] == str(test_equipo_reservable.id)
    assert created_reserva["proposito"] == "Reunión de planificación"
    assert created_reserva["notas_solicitante"] == "Necesita proyector"
    assert "estado" in created_reserva
    assert "id" in created_reserva

async def test_create_reserva_solapamiento(
    client: AsyncClient, auth_token_user: str,
    test_equipo_reservable: Equipo
):
    headers = {"Authorization": f"Bearer {auth_token_user}"}
    start1 = datetime.now(timezone.utc) + timedelta(days=2, hours=1)
    end1 = start1 + timedelta(hours=2)
    reserva1_schema = ReservaEquipoCreate(
        equipo_id=test_equipo_reservable.id,
        fecha_hora_inicio=start1,
        fecha_hora_fin=end1,
        proposito="Reserva 1",
        notas_solicitante="Test"
    )
    data1 = jsonable_encoder(reserva1_schema)
    response1 = await client.post(f"{settings.API_V1_STR}/reservas/", headers=headers, json=data1)
    assert response1.status_code == status.HTTP_201_CREATED

    start2 = start1 + timedelta(hours=1)
    end2 = start2 + timedelta(hours=2)
    reserva2_schema = ReservaEquipoCreate(
        equipo_id=test_equipo_reservable.id,
        fecha_hora_inicio=start2,
        fecha_hora_fin=end2,
        proposito="Reserva 2 Solapada",
        notas_solicitante="Test"
    )
    data2 = jsonable_encoder(reserva2_schema)
    response2 = await client.post(f"{settings.API_V1_STR}/reservas/", headers=headers, json=data2)
    assert response2.status_code == status.HTTP_409_CONFLICT
    assert "conflicto de reserva" in response2.json()["detail"].lower()

async def test_create_reserva_fecha_fin_antes_inicio(
    client: AsyncClient, auth_token_user: str, test_equipo_reservable: Equipo
):
    """
    Test mejorado: Ahora comprueba que la API devuelve un error HTTP 422,
    que es el comportamiento real definido en el servicio, en lugar de un ValueError local.
    """
    headers = {"Authorization": f"Bearer {auth_token_user}"}
    start_time = datetime.now(timezone.utc) + timedelta(days=3)
    end_time = start_time - timedelta(hours=1)

    reserva_schema = ReservaEquipoCreate(
        equipo_id=test_equipo_reservable.id,
        fecha_hora_inicio=start_time,
        fecha_hora_fin=end_time,
        proposito="Test Fechas Inválidas",
        notas_solicitante="Test"
    )
    data = jsonable_encoder(reserva_schema)
    response = await client.post(f"{settings.API_V1_STR}/reservas/", headers=headers, json=data)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

async def test_read_reservas_success(
    client: AsyncClient, auth_token_supervisor: str,
    test_equipo_reservable: Equipo,
    auth_token_user: str
):
    headers_user = {"Authorization": f"Bearer {auth_token_user}"}
    start = datetime.now(timezone.utc) + timedelta(days=4)
    end = start + timedelta(hours=1)
    reserva_schema = ReservaEquipoCreate(
        equipo_id=test_equipo_reservable.id,
        fecha_hora_inicio=start,
        fecha_hora_fin=end,
        proposito="Test Listar",
        notas_solicitante="Test"
    )
    data = jsonable_encoder(reserva_schema)
    await client.post(f"{settings.API_V1_STR}/reservas/", headers=headers_user, json=data)

    headers_supervisor = {"Authorization": f"Bearer {auth_token_supervisor}"}
    response = await client.get(f"{settings.API_V1_STR}/reservas/", headers=headers_supervisor)
    assert response.status_code == status.HTTP_200_OK
    reservas = response.json()
    assert isinstance(reservas, list)
    assert len(reservas) > 0

async def test_read_reserva_by_id_success(
    client: AsyncClient, auth_token_supervisor: str,
    test_equipo_reservable: Equipo,
    auth_token_user: str
):
    headers_user = {"Authorization": f"Bearer {auth_token_user}"}
    start = datetime.now(timezone.utc) + timedelta(days=5)
    end = start + timedelta(hours=1)
    reserva_schema = ReservaEquipoCreate(
        equipo_id=test_equipo_reservable.id,
        fecha_hora_inicio=start,
        fecha_hora_fin=end,
        proposito="Get ID Test",
        notas_solicitante="Test"
    )
    data = jsonable_encoder(reserva_schema)
    create_resp = await client.post(f"{settings.API_V1_STR}/reservas/", headers=headers_user, json=data)
    reserva_id = create_resp.json()["id"]

    headers_supervisor = {"Authorization": f"Bearer {auth_token_supervisor}"}
    response = await client.get(f"{settings.API_V1_STR}/reservas/{reserva_id}", headers=headers_supervisor)
    assert response.status_code == status.HTTP_200_OK
    reserva_data = response.json()
    assert reserva_data["id"] == reserva_id
    assert reserva_data["proposito"] == "Get ID Test"

async def test_update_reserva_propia_success(
    client: AsyncClient, auth_token_user: str,
    test_equipo_reservable: Equipo
):
    headers = {"Authorization": f"Bearer {auth_token_user}"}
    start = datetime.now(timezone.utc) + timedelta(days=6, hours=1)
    end = start + timedelta(hours=1)
    create_schema = ReservaEquipoCreate(
        equipo_id=test_equipo_reservable.id,
        fecha_hora_inicio=start,
        fecha_hora_fin=end,
        proposito="Original",
        notas_solicitante="Test"
    )
    create_data = jsonable_encoder(create_schema)
    create_resp = await client.post(f"{settings.API_V1_STR}/reservas/", headers=headers, json=create_data)
    reserva_id = create_resp.json()["id"]

    update_schema = ReservaEquipoUpdate(proposito="Propósito Actualizado por Usuario", notas_solicitante="Nota actualizada")
    update_data = jsonable_encoder(update_schema.model_dump(exclude_unset=True))
    update_response = await client.put(f"{settings.API_V1_STR}/reservas/{reserva_id}", headers=headers, json=update_data)
    assert update_response.status_code == status.HTTP_200_OK, f"Detalle error: {update_response.text}"
    updated_reserva = update_response.json()
    assert updated_reserva["id"] == reserva_id
    assert updated_reserva["proposito"] == "Propósito Actualizado por Usuario"

@pytest.fixture(scope="function")
async def reserva_pendiente(db: Session, test_user: Usuario, test_equipo_reservable: Equipo) -> ReservaEquipo:
    start = datetime.now(timezone.utc) + timedelta(days=7)
    end = start + timedelta(hours=1)
    reserva = ReservaEquipo(
        equipo_id=test_equipo_reservable.id,
        usuario_solicitante_id=test_user.id,
        fecha_hora_inicio=start,
        fecha_hora_fin=end,
        estado=EstadoReservaEnum.PENDIENTE_APROBACION.value,
        proposito="Reserva Pendiente",
        notas_solicitante="Test fixture"
    )
    db.add(reserva); db.commit(); db.refresh(reserva)
    return reserva

async def test_approve_reserva_success(
    client: AsyncClient, auth_token_supervisor: str,
    reserva_pendiente: ReservaEquipo
):
    headers = {"Authorization": f"Bearer {auth_token_supervisor}"}
    estado_data = {"estado": EstadoReservaEnum.CONFIRMADA.value, "notas_administrador": "Aprobada por test"}
    response = await client.patch(f"{settings.API_V1_STR}/reservas/{reserva_pendiente.id}/estado", headers=headers, json=estado_data)
    assert response.status_code == status.HTTP_200_OK, f"Detalle error: {response.text}"
    approved_reserva = response.json()
    assert approved_reserva["id"] == str(reserva_pendiente.id)
    assert approved_reserva["estado"] == EstadoReservaEnum.CONFIRMADA.value
    assert approved_reserva["aprobado_por_id"] is not None
    assert approved_reserva["fecha_aprobacion"] is not None

async def test_reject_reserva_success(
    client: AsyncClient, auth_token_supervisor: str,
    reserva_pendiente: ReservaEquipo
):
    headers = {"Authorization": f"Bearer {auth_token_supervisor}"}
    estado_data = {"estado": EstadoReservaEnum.RECHAZADA.value, "notas_administrador": "Equipo no disponible en esa fecha por mantenimiento."}
    response = await client.patch(f"{settings.API_V1_STR}/reservas/{reserva_pendiente.id}/estado", headers=headers, json=estado_data)
    assert response.status_code == status.HTTP_200_OK, f"Detalle error: {response.text}"
    rejected_reserva = response.json()
    assert rejected_reserva["id"] == str(reserva_pendiente.id)
    assert rejected_reserva["estado"] == EstadoReservaEnum.RECHAZADA.value
    assert rejected_reserva["notas_administrador"] == estado_data["notas_administrador"]

async def test_cancel_reserva_propia_success(
    client: AsyncClient, auth_token_user: str,
    test_equipo_reservable: Equipo
):
    headers = {"Authorization": f"Bearer {auth_token_user}"}
    start = datetime.now(timezone.utc) + timedelta(days=8)
    end = start + timedelta(hours=1)
    create_schema = ReservaEquipoCreate(
        equipo_id=test_equipo_reservable.id,
        fecha_hora_inicio=start,
        fecha_hora_fin=end,
        proposito="Para cancelar",
        notas_solicitante="Test"
    )
    create_data = jsonable_encoder(create_schema)
    create_resp = await client.post(f"{settings.API_V1_STR}/reservas/", headers=headers, json=create_data)
    reserva_id = create_resp.json()["id"]

    # Se usa el endpoint unificado PATCH
    cancel_response = await client.post(f"{settings.API_V1_STR}/reservas/{reserva_id}/cancelar", headers=headers)
    assert cancel_response.status_code == status.HTTP_200_OK, f"Detalle error: {cancel_response.text}"
    cancelled_reserva = cancel_response.json()
    assert cancelled_reserva["id"] == reserva_id
    # CORRECCIÓN: Se espera el valor correcto del Enum
    assert cancelled_reserva["estado"] == EstadoReservaEnum.CANCELADA_USUARIO.value
