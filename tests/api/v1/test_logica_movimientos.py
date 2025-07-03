import pytest
from httpx import AsyncClient
from fastapi import status
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models import Equipo, EstadoEquipo, TipoMantenimiento
from app.schemas.enums import TipoMovimientoEquipoEnum

pytestmark = pytest.mark.asyncio


async def test_mover_equipo_en_mantenimiento_falla(
    client: AsyncClient, db: Session, auth_token_supervisor: str,
    test_equipo_principal: Equipo, test_estado_mantenimiento: EstadoEquipo
):
    """
    Prueba que la lógica de negocio previene mover un equipo
    cuyo estado tiene 'permite_movimientos' como False.
    """
    headers = {"Authorization": f"Bearer {auth_token_supervisor}"}

    # 1. Poner equipo en estado "En Mantenimiento"
    test_equipo_principal.estado_id = test_estado_mantenimiento.id
    db.add(test_equipo_principal)
    db.commit()

    # 2. Intentar registrar un movimiento
    movimiento_data = {
        "equipo_id": str(test_equipo_principal.id),
        "tipo_movimiento": TipoMovimientoEquipoEnum.ASIGNACION_INTERNA.value,
        "destino": "Un lugar al que no puede ir",
        "origen": "Taller"
    }
    response = await client.post(f"{settings.API_V1_STR}/movimientos/", headers=headers, json=movimiento_data)

    # 3. Verificar el error
    assert response.status_code == status.HTTP_409_CONFLICT
    assert "no permite movimientos" in response.json()["detail"].lower()


async def test_eliminar_tipo_mantenimiento_en_uso_falla(
    client: AsyncClient, auth_token_admin: str,
    tipo_mantenimiento_preventivo: TipoMantenimiento,
    test_equipo_principal: Equipo
):
    """
    Prueba que la integridad referencial (ON DELETE RESTRICT) de la DB
    impide eliminar un catálogo (TipoMantenimiento) si está en uso.
    """
    headers = {"Authorization": f"Bearer {auth_token_admin}"}

    # 1. Crear una entidad que use el catálogo (un mantenimiento) A TRAVÉS DE LA API
    mantenimiento_data = {
        "equipo_id": str(test_equipo_principal.id),
        "tipo_mantenimiento_id": str(tipo_mantenimiento_preventivo.id),
        "tecnico_responsable": "Test de Integridad API",
        "estado": "Programado"
    }
    create_response = await client.post(
        f"{settings.API_V1_STR}/mantenimientos/",
        headers=headers,
        json=mantenimiento_data
    )
    assert create_response.status_code == status.HTTP_201_CREATED, "Fallo al crear el mantenimiento de prueba"

    # 2. Intentar borrar el tipo de mantenimiento que ahora está en uso
    response = await client.delete(
        f"{settings.API_V1_STR}/catalogos/tipos-mantenimiento/{tipo_mantenimiento_preventivo.id}",
        headers=headers
    )

    # 3. Verificar el error de conflicto
    assert response.status_code == status.HTTP_409_CONFLICT
    assert "está en uso" in response.json()["detail"].lower()
