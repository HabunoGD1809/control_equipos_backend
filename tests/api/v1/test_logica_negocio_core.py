from tests.helpers import technician_id, employee_id
from app.models import Marca, Ubicacion
from tests.helpers import catalog_id, location_id, employee_id
from uuid import uuid4
import pytest
from httpx import AsyncClient
from fastapi import status
from sqlalchemy.orm import Session
from datetime import date, timedelta
from app.core.config import settings
from app.models import Equipo, EstadoEquipo, TipoMantenimiento, Mantenimiento
from app.schemas.enums import TipoMovimientoEquipoEnum
pytestmark = pytest.mark.asyncio

@pytest.fixture(scope='function')
def estado_no_movible(db: Session) -> EstadoEquipo:
    """Crea un estado de equipo que explícitamente no permite movimientos."""
    estado = EstadoEquipo(nombre='En Mantenimiento Test', descripcion='Estado para probar reglas de no-movimiento', permite_movimientos=False, color_hex='#FFA500')
    db.add(estado)
    db.commit()
    db.refresh(estado)
    return estado

async def test_mover_equipo_en_estado_no_movible_falla(client: AsyncClient, db: Session, auth_token_supervisor: str, test_equipo_principal: Equipo, estado_no_movible: EstadoEquipo):
    """
    Prueba que la lógica de negocio previene mover un equipo
    cuyo estado tiene 'permite_movimientos' como False.
    """
    headers = {'Authorization': f'Bearer {auth_token_supervisor}'}
    test_equipo_principal.estado_id = estado_no_movible.id
    db.add(test_equipo_principal)
    db.commit()
    movimiento_data = {'equipo_id': str(test_equipo_principal.id), 'tipo_movimiento': TipoMovimientoEquipoEnum.ASIGNACION_INTERNA.value, 'ubicacion_destino_id': str(location_id(db, 'Un lugar al que no puede ir')), 'ubicacion_origen_id': None, 'empleado_destino_id': str(employee_id(db))}
    response = await client.post(f'{settings.API_V1_STR}/movimientos/', headers=headers, json=movimiento_data)
    assert response.status_code == status.HTTP_409_CONFLICT
    assert 'no permite movimientos' in response.json()['detail'].lower()

async def test_eliminar_catalogo_en_uso_falla(client: AsyncClient, db: Session, auth_token_admin: str, tipo_mantenimiento_preventivo: TipoMantenimiento, test_equipo_principal: Equipo):
    """
    Prueba que la integridad referencial (ON DELETE RESTRICT) de la DB
    impide eliminar un catálogo (TipoMantenimiento) si está en uso.
    """
    headers = {'Authorization': f'Bearer {auth_token_admin}'}
    mantenimiento = Mantenimiento(equipo_id=test_equipo_principal.id, tipo_mantenimiento_id=tipo_mantenimiento_preventivo.id, tecnico_id=technician_id(db, 'Test de Integridad'))
    db.add(mantenimiento)
    db.commit()
    response = await client.delete(f'{settings.API_V1_STR}/catalogos/tipos-mantenimiento/{tipo_mantenimiento_preventivo.id}', headers=headers)
    assert response.status_code == status.HTTP_409_CONFLICT
    assert 'está en uso y no puede ser eliminado' in response.json()['detail'].lower()

async def test_create_equipo_fechas_invalidas_falla(client: AsyncClient, auth_token_supervisor: str, test_estado_disponible: EstadoEquipo):
    """Prueba que la DB constraint 'check_fechas_logicas' en la tabla Equipos funcione."""
    headers = {'Authorization': f'Bearer {auth_token_supervisor}'}
    numero_serie_valido = f'SER-FEC-{uuid4().hex[:8].upper()}'
    equipo_data = {'nombre': 'Equipo Fechas Inválidas', 'numero_serie': numero_serie_valido, 'estado_id': str(test_estado_disponible.id), 'fecha_adquisicion': date.today().isoformat(), 'fecha_puesta_marcha': (date.today() - timedelta(days=1)).isoformat()}
    response = await client.post(f'{settings.API_V1_STR}/equipos/', headers=headers, json=equipo_data)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert 'violates check constraint' in response.json()['detail'].lower()
    assert 'check_fechas_logicas' in response.json()['detail'].lower()
