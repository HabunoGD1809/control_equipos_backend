from app.models import Marca, Ubicacion
from tests.helpers import catalog_id, location_id, employee_id
import time
import pytest
from httpx import AsyncClient
from app.models import Usuario, TipoItemInventario, InventarioStock, LicenciaSoftware, Equipo, Rol
from decimal import Decimal
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.estado_equipo import EstadoEquipo
pytestmark = pytest.mark.asyncio

async def test_trigger_actualizar_inventario_stock_fn(client: AsyncClient, auth_token_admin: str, stock_inicial_toner: InventarioStock, test_equipo_reservable: Equipo, test_tecnico_fixture: Usuario, db):
    """
    Verifica que el trigger de inventario ('actualizar_inventario_stock_fn')
    reduce correctamente el stock al registrar una 'Salida Uso'.
    """
    admin_headers = {'Authorization': f'Bearer {auth_token_admin}'}
    cantidad_inicial = stock_inicial_toner.cantidad_actual
    costo_unitario_salida = Decimal('26.00')
    movimiento_data = {'tipo_item_id': str(stock_inicial_toner.tipo_item_id), 'tipo_movimiento': 'Salida Uso', 'cantidad': 1, 'ubicacion_origen_id': str(location_id(db, str(stock_inicial_toner.ubicacion_id))), 'lote_origen': stock_inicial_toner.lote, 'equipo_asociado_id': str(test_equipo_reservable.id), 'usuario_id': str(test_tecnico_fixture.id), 'costo_unitario': str(costo_unitario_salida), 'notas': 'Prueba de trigger de salida de inventario'}
    response = await client.post('/api/v1/inventario/movimientos/', json=movimiento_data, headers=admin_headers)
    assert response.status_code == 201, 'El movimiento de inventario debió crearse.'
    params = {'tipo_item_id': str(stock_inicial_toner.tipo_item_id), 'ubicacion_id': str(location_id(db, str(stock_inicial_toner.ubicacion_id))), 'lote': stock_inicial_toner.lote}
    response_stock = await client.get('/api/v1/inventario/stock/', headers=admin_headers, params=params)
    assert response_stock.status_code == 200, 'La consulta de stock después del movimiento falló.'
    stock_data = response_stock.json()
    assert len(stock_data) > 0, 'No se encontró el registro de stock después del movimiento.'
    stock_actualizado = stock_data[0]
    assert stock_actualizado['cantidad_actual'] == cantidad_inicial - 1, 'El trigger no redujo la cantidad del stock correctamente.'

async def test_trigger_actualizar_licencia_disponible_fn(client: AsyncClient, auth_token_admin: str, licencia_office_disponible: LicenciaSoftware, equipo_sin_licencia: Equipo):
    """
    Verifica que el trigger 'actualizar_licencia_disponible_fn' reduce la
    cantidad disponible al asignar una licencia y la aumenta al eliminar la asignación.
    """
    admin_headers = {'Authorization': f'Bearer {auth_token_admin}'}
    licencia_id = str(licencia_office_disponible.id)
    cantidad_inicial = licencia_office_disponible.cantidad_disponible
    asignacion_data = {'licencia_id': licencia_id, 'equipo_id': str(equipo_sin_licencia.id)}
    response_asig = await client.post('/api/v1/licencias/asignaciones/', json=asignacion_data, headers=admin_headers)
    assert response_asig.status_code == 201
    asignacion_id = response_asig.json()['id']
    response_lic_after_asig = await client.get(f'/api/v1/licencias/{licencia_id}', headers=admin_headers)
    lic_after_asig = response_lic_after_asig.json()
    assert lic_after_asig['cantidad_disponible'] == cantidad_inicial - 1, 'El trigger no restó una licencia disponible tras la asignación.'
    response_del = await client.delete(f'/api/v1/licencias/asignaciones/{asignacion_id}', headers=admin_headers)
    assert response_del.status_code == 200
    response_lic_after_del = await client.get(f'/api/v1/licencias/{licencia_id}', headers=admin_headers)
    lic_after_del = response_lic_after_del.json()
    assert lic_after_del['cantidad_disponible'] == cantidad_inicial, 'El trigger no devolvió la licencia disponible tras eliminar la asignación.'

async def test_audit_trigger_on_equipment_update(client: AsyncClient, auth_token_admin: str, test_equipo_reservable: Equipo, db):
    """
    Verifica que el trigger de auditoría ('audit_trigger_fn') crea un registro
    en la tabla 'audit_log' cuando se actualiza un equipo.
    """
    admin_headers = {'Authorization': f'Bearer {auth_token_admin}'}
    equipo_id = str(test_equipo_reservable.id)
    response_orig = await client.get(f'/api/v1/equipos/{equipo_id}', headers=admin_headers)
    equipo_original = response_orig.json()
    nueva_ubicacion = f'Ubicación Auditada {int(time.time())}'
    update_data = {'ubicacion_id': str(location_id(db, nueva_ubicacion))}
    response_update = await client.put(f'/api/v1/equipos/{equipo_id}', json=update_data, headers=admin_headers)
    assert response_update.status_code == 200
    response_audit = await client.get(f'/api/v1/auditoria/?table_name=equipos&limit=5', headers=admin_headers)
    assert response_audit.status_code == 200, 'Se necesita un endpoint para leer la auditoría para esta prueba.'
    audit_logs = response_audit.json()
    assert len(audit_logs) > 0, 'No se encontraron registros de auditoría para la tabla equipos.'
    found_log = None
    for log in audit_logs:
        if log['operation'] == 'UPDATE' and log['new_data']['id'] == equipo_id:
            found_log = log
            break
    assert found_log is not None, 'No se encontró el registro de auditoría para la actualización específica.'
    assert found_log['old_data']['ubicacion_id'] == equipo_original['ubicacion_id']
    assert found_log['new_data']['ubicacion_id'] == str(location_id(db, nueva_ubicacion))
    assert found_log['table_name'] == 'equipos'

async def test_on_delete_restrict_for_estado_equipo(client: AsyncClient, auth_token_admin: str, test_equipo_reservable: Equipo):
    """
    Verifica que la restricción ON DELETE RESTRICT impide borrar un 'EstadoEquipo'
    que está siendo utilizado por al menos un 'Equipo'.
    """
    admin_headers = {'Authorization': f'Bearer {auth_token_admin}'}
    estado_id_en_uso = str(test_equipo_reservable.estado_id)
    response = await client.delete(f'{settings.API_V1_STR}/catalogos/estados-equipo/{estado_id_en_uso}', headers=admin_headers)
    assert response.status_code == 409, 'Debe fallar con 409 Conflict al intentar borrar un estado en uso.'
    error_detail = response.json()['detail'].lower()
    assert 'está en uso' in error_detail or 'violates foreign key constraint' in error_detail, 'El mensaje debe indicar que el recurso no se puede borrar por estar en uso.'

async def test_on_delete_cascade_for_rol(client: AsyncClient, auth_token_admin: str, create_test_rol: Rol, db: Session):
    """
    Verifica que la restricción ON DELETE CASCADE en 'roles_permisos' funciona.
    Al borrar un Rol, sus asignaciones de permisos deben desaparecer.
    """
    from app.models import RolPermiso
    admin_headers = {'Authorization': f'Bearer {auth_token_admin}'}
    rol_id = str(create_test_rol.id)
    permisos_antes = db.query(RolPermiso).filter(RolPermiso.rol_id == rol_id).count()
    assert permisos_antes > 0, 'El rol de prueba debe tener permisos asignados antes de borrarlo.'
    response = await client.delete(f'{settings.API_V1_STR}/gestion/roles/{rol_id}', headers=admin_headers)
    assert response.status_code == 200, 'El rol debió ser borrado exitosamente.'
    db.expire_all()
    permisos_despues = db.query(RolPermiso).filter(RolPermiso.rol_id == rol_id).count()
    assert permisos_despues == 0, 'Los permisos asociados al rol debieron ser eliminados en cascada.'
