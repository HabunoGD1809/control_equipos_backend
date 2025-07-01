import pytest
from httpx import AsyncClient
from fastapi import status
from datetime import datetime, timedelta, timezone, date
from uuid import uuid4

from app.core.config import settings
from app.models.equipo import Equipo
from app.models.estado_equipo import EstadoEquipo
from sqlalchemy.orm import Session

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
    assert "conflicto de reserva" in error_detail or "ya existe una reserva" in error_detail

@pytest.mark.asyncio
async def test_reservar_equipo_en_mantenimiento_falla(
    client: AsyncClient,
    auth_token_usuario_regular: str,
    db: Session,
    test_equipo_principal: Equipo,
    test_estado_mantenimiento: EstadoEquipo
):
    """
    Prueba de lógica de negocio: no se debería poder reservar un equipo
    cuyo estado no es 'Disponible' (ej. 'En Mantenimiento').
    """
    headers = {"Authorization": f"Bearer {auth_token_usuario_regular}"}
    
    # 1. Cambiar el estado del equipo a "En Mantenimiento"
    test_equipo_principal.estado_id = test_estado_mantenimiento.id
    db.add(test_equipo_principal)
    db.commit()

    # 2. Intentar crear una reserva para este equipo
    start_time = datetime.now(timezone.utc) + timedelta(days=2)
    end_time = start_time + timedelta(hours=2)
    reserva_data = {
        "equipo_id": str(test_equipo_principal.id),
        "fecha_hora_inicio": start_time.isoformat(),
        "fecha_hora_fin": end_time.isoformat(),
        "proposito": "Reserva de equipo no disponible"
    }
    response = await client.post(f"{settings.API_V1_STR}/reservas/", headers=headers, json=reserva_data)

    # 3. Verificar que la API responde con un error (ej. 400 Bad Request o 409 Conflict)
    assert response.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_409_CONFLICT], response.text
    error_detail = response.json().get("detail", "").lower()
    assert "no está disponible para ser reservado" in error_detail
