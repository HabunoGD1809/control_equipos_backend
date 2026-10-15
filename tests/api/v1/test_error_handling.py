from app.models import Marca, Ubicacion
from tests.helpers import catalog_id, location_id, employee_id
import pytest
from httpx import AsyncClient
import uuid
import random
import string
from app.models import Equipo
pytestmark = pytest.mark.asyncio

def generate_correct_format_serie(prefix: str) -> str:
    """Genera un número de serie con el formato XXX-####-XXX."""
    p = (prefix.upper() + 'XXX')[:3]
    nums = ''.join(random.choices(string.digits, k=4))
    suffix = ''.join(random.choices(string.ascii_uppercase, k=3))
    return f'{p}-{nums}-{suffix}'

async def test_create_with_nonexistent_foreign_key_fails(client: AsyncClient, auth_token_admin: str, db):
    """
    Intenta crear un equipo con un 'estado_id' que no existe en la tabla 'estados_equipo'.
    Debe fallar con un error 404.
    """
    admin_headers = {'Authorization': f'Bearer {auth_token_admin}'}
    equipo_data = {'nombre': 'Equipo con FK Invalida', 'numero_serie': generate_correct_format_serie('FKF'), 'estado_id': str(uuid.uuid4()), 'marca_id': str(catalog_id(db, Marca, 'ErrorBrand')), 'modelo': 'FailModel'}
    response = await client.post('/api/v1/equipos/', json=equipo_data, headers=admin_headers)
    assert response.status_code == 404, f'Se esperaba 404 pero se recibió {response.status_code}: {response.text}'
    error_detail = response.json()['detail'].lower()
    assert 'estado de equipo' in error_detail and 'no encontrado' in error_detail

async def test_unique_constraint_violation_on_create(client: AsyncClient, auth_token_admin: str, test_equipo_reservable: Equipo, db):
    admin_headers = {'Authorization': f'Bearer {auth_token_admin}'}
    equipo_data_duplicado = {'nombre': 'Equipo Duplicado', 'numero_serie': test_equipo_reservable.numero_serie, 'estado_id': str(test_equipo_reservable.estado_id), 'marca_id': str(catalog_id(db, Marca, 'DuplicateBrand')), 'modelo': 'CopyModel'}
    response = await client.post('/api/v1/equipos/', json=equipo_data_duplicado, headers=admin_headers)
    assert response.status_code == 409, 'Debe devolver 409 Conflict por violación de restricción UNIQUE.'
    error_detail = response.json()['detail'].lower()
    assert 'número de serie ya registrado' in error_detail
