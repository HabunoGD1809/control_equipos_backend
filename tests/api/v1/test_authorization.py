from tests.helpers import technician_id, employee_id
from app.models import Marca, Ubicacion
from tests.helpers import catalog_id, location_id, employee_id
import pytest
from httpx import AsyncClient
from app.models import Usuario, Equipo, EstadoEquipo
import uuid
from fastapi import Depends, HTTPException, status, Request
from tests.api.v1.test_equipos import generate_valid_serie
pytestmark = pytest.mark.asyncio

@pytest.fixture(scope='function')
def test_estado_averiado(db) -> EstadoEquipo:
    """Fixture para asegurar que existe el estado 'Averiado' que requiere autorización."""
    estado = db.query(EstadoEquipo).filter(EstadoEquipo.nombre == 'Averiado').first()
    if not estado:
        estado = EstadoEquipo(nombre='Averiado', descripcion='Requiere mantenimiento/reparación', permite_movimientos=True, requiere_autorizacion=True, color_hex='#F44336', es_estado_final=False)
        db.add(estado)
        db.commit()
    elif not estado.permite_movimientos:
        estado.permite_movimientos = True
        db.commit()
    return estado

async def test_tecnico_cannot_authorize_movement_requiring_it(client: AsyncClient, auth_token_tecnico: str, auth_token_admin: str, test_estado_averiado: EstadoEquipo, db):
    """
    PRUEBA DE PERMISOS: Un 'tecnico' no puede mover un equipo cuyo estado requiere autorización.
    """
    admin_headers = {'Authorization': f'Bearer {auth_token_admin}'}
    tecnico_headers = {'Authorization': f'Bearer {auth_token_tecnico}'}
    equipo_data = {'nombre': 'Equipo que Requiere Autorización', 'numero_serie': generate_valid_serie('AUTH'), 'estado_id': str(test_estado_averiado.id), 'marca_id': str(catalog_id(db, Marca, 'Test')), 'modelo': 'Auth'}
    response_create = await client.post('/api/v1/equipos/', json=equipo_data, headers=admin_headers)
    assert response_create.status_code == 201
    equipo_id = response_create.json()['id']
    movimiento_data = {'equipo_id': equipo_id, 'tipo_movimiento': 'Transferencia Bodega', 'ubicacion_origen_id': None, 'ubicacion_destino_id': str(location_id(db, 'Recepción')), 'proposito': 'Intento de movimiento por técnico sin permiso de autorización', 'empleado_destino_id': str(employee_id(db))}
    response_tecnico = await client.post('/api/v1/movimientos/', json=movimiento_data, headers=tecnico_headers)
    assert response_tecnico.status_code == status.HTTP_201_CREATED
    assert response_tecnico.json()['estado'] == 'Pendiente'
    movement_id = response_tecnico.json()['id']
    approval = await client.patch(f'/api/v1/movimientos/{movement_id}/estado', json={'estado': 'Autorizado'}, headers=tecnico_headers)
    assert approval.status_code == status.HTTP_403_FORBIDDEN
    unchanged = await client.get(f'/api/v1/equipos/{equipo_id}', headers=admin_headers)
    assert unchanged.json()['estado_id'] == str(test_estado_averiado.id)
