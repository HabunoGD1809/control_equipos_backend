import pytest
from httpx import AsyncClient
from fastapi import status
from datetime import datetime, timedelta, timezone
from uuid import UUID

from app.core.config import settings
from app.models import Equipo, EstadoEquipo, ReservaEquipo
from sqlalchemy.orm import Session
from app.schemas.enums import EstadoReservaEnum

pytestmark = pytest.mark.asyncio

@pytest.mark.asyncio
async def test_crear_reserva_solapada_falla(
    client: AsyncClient,
    auth_token_usuario_regular: str,
    test_equipo_reservable: Equipo
):
    """
    Prueba que la API previene la creación de una segunda reserva que se solape
    en tiempo con una ya existente para el mismo equipo.
    """
    headers = {"Authorization": f"Bearer {auth_token_usuario_regular}"}
    start_time = datetime.now(timezone.utc) + timedelta(days=1)
    end_time = start_time + timedelta(hours=2)

    # 1. Crear la primera reserva con éxito
    reserva_data_1 = {
        "equipo_id": str(test_equipo_reservable.id),
        "fecha_hora_inicio": start_time.isoformat(),
        "fecha_hora_fin": end_time.isoformat(),
        "proposito": "Reserva inicial para prueba de solapamiento"
    }
    response1 = await client.post(f"{settings.API_V1_STR}/reservas/", headers=headers, json=reserva_data_1)
    assert response1.status_code == status.HTTP_201_CREATED, response1.text

    # 2. Intentar crear una segunda reserva que se solapa
    start_time_2 = start_time + timedelta(hours=1)
    end_time_2 = start_time_2 + timedelta(hours=2)
    reserva_data_2 = {
        "equipo_id": str(test_equipo_reservable.id),
        "fecha_hora_inicio": start_time_2.isoformat(),
        "fecha_hora_fin": end_time_2.isoformat(),
        "proposito": "Reserva solapada que debería fallar"
    }
    response2 = await client.post(f"{settings.API_V1_STR}/reservas/", headers=headers, json=reserva_data_2)

    # 3. Verificar que la API devuelve un error de conflicto (409)
    assert response2.status_code == status.HTTP_409_CONFLICT, response2.text
    error_detail = response2.json().get("detail", "").lower()
    assert "conflicto de reserva" in error_detail or "ya está reservado" in error_detail

@pytest.mark.asyncio
async def test_reservar_equipo_en_mantenimiento_falla(
    client: AsyncClient,
    auth_token_usuario_regular: str,
    db: Session,
    test_equipo_principal: Equipo,
    test_estado_mantenimiento: EstadoEquipo
):
    """
    Prueba que no se puede reservar un equipo cuyo estado no es 'Disponible'.
    """
    headers = {"Authorization": f"Bearer {auth_token_usuario_regular}"}
    
    # Poner el equipo en estado de mantenimiento
    test_equipo_principal.estado_id = test_estado_mantenimiento.id
    db.add(test_equipo_principal)
    db.commit()

    start_time = datetime.now(timezone.utc) + timedelta(days=2)
    end_time = start_time + timedelta(hours=2)
    reserva_data = {
        "equipo_id": str(test_equipo_principal.id),
        "fecha_hora_inicio": start_time.isoformat(),
        "fecha_hora_fin": end_time.isoformat(),
        "proposito": "Reserva de equipo no disponible"
    }
    response = await client.post(f"{settings.API_V1_STR}/reservas/", headers=headers, json=reserva_data)

    assert response.status_code == status.HTTP_409_CONFLICT, response.text
    assert "no está disponible para ser reservado" in response.json()["detail"].lower()

@pytest.mark.asyncio
async def test_full_reserva_lifecycle_and_edge_cases(
    client: AsyncClient,
    auth_token_usuario_regular: str,
    auth_token_supervisor: str,
    test_equipo_reservable: Equipo
):
    """
    Prueba el ciclo de vida completo de una reserva y casos de borde:
    1. Creación por un usuario regular.
    2. Fallo al intentar hacer check-in si no está aprobada.
    3. Aprobación por un supervisor.
    4. Éxito al hacer check-in.
    5. Fallo al intentar hacer check-in de nuevo.
    6. Fallo al intentar hacer check-out antes de tiempo.
    7. Éxito al hacer check-out.
    """
    headers_user = {"Authorization": f"Bearer {auth_token_usuario_regular}"}
    headers_supervisor = {"Authorization": f"Bearer {auth_token_supervisor}"}
    start_time = datetime.now(timezone.utc) + timedelta(days=5) # Usar una fecha lejana para evitar solapamientos
    end_time = start_time + timedelta(hours=2)

    # 1. Creación por un usuario regular (queda como 'Pendiente Aprobacion')
    create_data = {
        "equipo_id": str(test_equipo_reservable.id),
        "fecha_hora_inicio": start_time.isoformat(),
        "fecha_hora_fin": end_time.isoformat(),
        "proposito": "Reserva para prueba de ciclo de vida completo"
    }
    create_response = await client.post(f"{settings.API_V1_STR}/reservas/", headers=headers_user, json=create_data)
    assert create_response.status_code == status.HTTP_201_CREATED
    reserva = create_response.json()
    reserva_id = reserva["id"]
    assert reserva["estado"] == EstadoReservaEnum.PENDIENTE_APROBACION.value

    # 2. Fallo al intentar hacer check-in si no está aprobada
    checkin_data = {"check_in_time": datetime.now(timezone.utc).isoformat()}
    response_fail_checkin = await client.patch(f"{settings.API_V1_STR}/reservas/{reserva_id}/check-in-out", headers=headers_supervisor, json=checkin_data)
    assert response_fail_checkin.status_code == status.HTTP_409_CONFLICT
    assert "solo se puede hacer check-in de reservas en estado 'confirmada'" in response_fail_checkin.json()["detail"].lower()

    # 3. Aprobación por un supervisor
    estado_data_aprobar = {"estado": EstadoReservaEnum.CONFIRMADA.value, "notas_administrador": "Aprobado para la prueba"}
    response_approve = await client.patch(f"{settings.API_V1_STR}/reservas/{reserva_id}/estado", headers=headers_supervisor, json=estado_data_aprobar)
    assert response_approve.status_code == status.HTTP_200_OK
    assert response_approve.json()["estado"] == EstadoReservaEnum.CONFIRMADA.value

    # 4. Éxito al hacer check-in
    checkin_time = datetime.now(timezone.utc)
    checkin_data = {"check_in_time": checkin_time.isoformat()}
    response_checkin = await client.patch(f"{settings.API_V1_STR}/reservas/{reserva_id}/check-in-out", headers=headers_supervisor, json=checkin_data)
    assert response_checkin.status_code == status.HTTP_200_OK
    assert response_checkin.json()["estado"] == EstadoReservaEnum.EN_CURSO.value
    assert response_checkin.json()["check_in_time"] is not None

    # 5. Fallo al intentar hacer check-in de nuevo
    response_checkin_again = await client.patch(f"{settings.API_V1_STR}/reservas/{reserva_id}/check-in-out", headers=headers_supervisor, json=checkin_data)
    assert response_checkin_again.status_code == status.HTTP_409_CONFLICT
    
    # 6. Fallo al intentar hacer check-out con un check-in en el JSON (simulando un error de cliente)
    bad_checkout_data = {"check_in_time": checkin_time.isoformat(), "check_out_time": datetime.now(timezone.utc).isoformat()}
    response_fail_checkout = await client.patch(f"{settings.API_V1_STR}/reservas/{reserva_id}/check-in-out", headers=headers_supervisor, json=bad_checkout_data)
    assert response_fail_checkout.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # 7. Éxito al hacer check-out
    checkout_time = datetime.now(timezone.utc)
    checkout_data = {"check_out_time": checkout_time.isoformat(), "notas_devolucion": "Equipo devuelto OK."}
    response_checkout = await client.patch(f"{settings.API_V1_STR}/reservas/{reserva_id}/check-in-out", headers=headers_supervisor, json=checkout_data)
    assert response_checkout.status_code == status.HTTP_200_OK
    checked_out_reserva = response_checkout.json()
    assert checked_out_reserva["estado"] == EstadoReservaEnum.FINALIZADA.value
    assert checked_out_reserva["check_out_time"] is not None
    assert checked_out_reserva["notas_devolucion"] == "Equipo devuelto OK."


@pytest.mark.asyncio
async def test_supervisor_crea_reserva_y_se_confirma_auto(
    client: AsyncClient,
    auth_token_supervisor: str,
    test_equipo_reservable: Equipo,
):
    """
    PRUEBA DE LÓGICA CLAVE:
    Un usuario con permiso de 'aprobar_reservas' (como el supervisor)
    debería tener sus reservas confirmadas automáticamente al crearlas.
    """
    headers = {"Authorization": f"Bearer {auth_token_supervisor}"}
    start_time = datetime.now(timezone.utc) + timedelta(days=10)
    end_time = start_time + timedelta(hours=2)

    create_data = {
        "equipo_id": str(test_equipo_reservable.id),
        "fecha_hora_inicio": start_time.isoformat(),
        "fecha_hora_fin": end_time.isoformat(),
        "proposito": "Reserva de supervisor (auto-confirmada)"
    }
    response = await client.post(f"{settings.API_V1_STR}/reservas/", headers=headers, json=create_data)
    
    assert response.status_code == status.HTTP_201_CREATED, response.text
    reserva = response.json()
    assert reserva["estado"] == EstadoReservaEnum.CONFIRMADA.value, \
        "La reserva de un supervisor debería auto-confirmarse."

@pytest.mark.asyncio
async def test_usuario_regular_crea_reserva_y_queda_pendiente(
    client: AsyncClient,
    auth_token_usuario_regular: str,
    test_equipo_reservable: Equipo,
):
    """
    PRUEBA DE LÓGICA CLAVE:
    Un usuario sin permiso de 'aprobar_reservas' (como el usuario regular)
    debería crear una reserva que quede en estado 'Pendiente Aprobacion'.
    """
    headers = {"Authorization": f"Bearer {auth_token_usuario_regular}"}
    start_time = datetime.now(timezone.utc) + timedelta(days=11)
    end_time = start_time + timedelta(hours=2)

    create_data = {
        "equipo_id": str(test_equipo_reservable.id),
        "fecha_hora_inicio": start_time.isoformat(),
        "fecha_hora_fin": end_time.isoformat(),
        "proposito": "Reserva de usuario regular (debe quedar pendiente)"
    }
    response = await client.post(f"{settings.API_V1_STR}/reservas/", headers=headers, json=create_data)
    
    assert response.status_code == status.HTTP_201_CREATED, response.text
    reserva = response.json()
    assert reserva["estado"] == EstadoReservaEnum.PENDIENTE_APROBACION.value, \
        "La reserva de un usuario regular debería quedar 'Pendiente Aprobacion'."

@pytest.mark.asyncio
async def test_approve_checkin_checkout_flow(
    client: AsyncClient,
    auth_token_usuario_regular: str,
    auth_token_supervisor: str,
    test_equipo_reservable: Equipo
):
    """
    Prueba el flujo de aprobación y uso de una reserva creada por un usuario regular.
    """
    headers_user = {"Authorization": f"Bearer {auth_token_usuario_regular}"}
    headers_supervisor = {"Authorization": f"Bearer {auth_token_supervisor}"}
    start_time = datetime.now(timezone.utc) + timedelta(days=12)
    end_time = start_time + timedelta(hours=2)

    # 1. Usuario Regular crea una reserva (debería quedar Pendiente)
    create_data = {
        "equipo_id": str(test_equipo_reservable.id),
        "fecha_hora_inicio": start_time.isoformat(),
        "fecha_hora_fin": end_time.isoformat(),
        "proposito": "Reserva para prueba de ciclo de vida"
    }
    create_response = await client.post(f"{settings.API_V1_STR}/reservas/", headers=headers_user, json=create_data)
    assert create_response.status_code == status.HTTP_201_CREATED
    reserva_id = create_response.json()["id"]

    # 2. Supervisor la aprueba
    estado_data_aprobar = {"estado": EstadoReservaEnum.CONFIRMADA.value}
    response_approve = await client.patch(f"{settings.API_V1_STR}/reservas/{reserva_id}/estado", headers=headers_supervisor, json=estado_data_aprobar)
    assert response_approve.status_code == status.HTTP_200_OK
    assert response_approve.json()["estado"] == EstadoReservaEnum.CONFIRMADA.value

    # 3. Supervisor realiza el Check-in
    checkin_data = {"check_in_time": datetime.now(timezone.utc).isoformat()}
    response_checkin = await client.patch(f"{settings.API_V1_STR}/reservas/{reserva_id}/check-in-out", headers=headers_supervisor, json=checkin_data)
    assert response_checkin.status_code == status.HTTP_200_OK
    assert response_checkin.json()["estado"] == EstadoReservaEnum.EN_CURSO.value

    # 4. Supervisor realiza el Check-out
    checkout_data = {"check_out_time": datetime.now(timezone.utc).isoformat()}
    response_checkout = await client.patch(f"{settings.API_V1_STR}/reservas/{reserva_id}/check-in-out", headers=headers_supervisor, json=checkout_data)
    assert response_checkout.status_code == status.HTTP_200_OK
    assert response_checkout.json()["estado"] == EstadoReservaEnum.FINALIZADA.value
