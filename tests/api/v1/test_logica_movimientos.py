from tests.helpers import technician_id, employee_id
from app.models import Marca, Ubicacion
from tests.helpers import catalog_id, location_id, employee_id
import pytest
from httpx import AsyncClient
from fastapi import status
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models import Equipo, EstadoEquipo, TipoMantenimiento
from app.schemas.enums import TipoMovimientoEquipoEnum
pytestmark = pytest.mark.asyncio

async def test_mover_equipo_en_mantenimiento_falla(client: AsyncClient, db: Session, auth_token_supervisor: str, test_equipo_principal: Equipo, test_estado_mantenimiento: EstadoEquipo):
    """
    Prueba que la lógica de negocio previene mover un equipo
    cuyo estado tiene 'permite_movimientos' como False.
    """
    headers = {'Authorization': f'Bearer {auth_token_supervisor}'}
    test_equipo_principal.estado_id = test_estado_mantenimiento.id
    db.add(test_equipo_principal)
    db.commit()
    movimiento_data = {'equipo_id': str(test_equipo_principal.id), 'tipo_movimiento': TipoMovimientoEquipoEnum.ASIGNACION_INTERNA.value, 'ubicacion_destino_id': str(location_id(db, 'Un lugar al que no puede ir')), 'ubicacion_origen_id': None, 'empleado_destino_id': str(employee_id(db))}
    response = await client.post(f'{settings.API_V1_STR}/movimientos/', headers=headers, json=movimiento_data)
    assert response.status_code == status.HTTP_409_CONFLICT
    assert 'no permite movimientos' in response.json()['detail'].lower()

async def test_eliminar_tipo_mantenimiento_en_uso_falla(client: AsyncClient, auth_token_admin: str, tipo_mantenimiento_preventivo: TipoMantenimiento, test_equipo_principal: Equipo, db):
    """
    Prueba que la integridad referencial (ON DELETE RESTRICT) de la DB
    impide eliminar un catálogo (TipoMantenimiento) si está en uso.
    """
    headers = {'Authorization': f'Bearer {auth_token_admin}'}
    mantenimiento_data = {'equipo_id': str(test_equipo_principal.id), 'tipo_mantenimiento_id': str(tipo_mantenimiento_preventivo.id), 'tecnico_id': str(technician_id(db, 'Test de Integridad API')), 'estado': 'Programado'}
    create_response = await client.post(f'{settings.API_V1_STR}/mantenimientos/', headers=headers, json=mantenimiento_data)
    assert create_response.status_code == status.HTTP_201_CREATED, 'Fallo al crear el mantenimiento de prueba'
    response = await client.delete(f'{settings.API_V1_STR}/catalogos/tipos-mantenimiento/{tipo_mantenimiento_preventivo.id}', headers=headers)
    assert response.status_code == status.HTTP_409_CONFLICT
    assert 'está en uso' in response.json()['detail'].lower()
