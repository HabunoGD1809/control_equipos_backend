from uuid import UUID
from sqlalchemy import select
from app.models import Ubicacion, Empleado, Tecnico
from tests.conftest import catalog_id


def location_id(db, value):
    if value is None:
        return None
    try:
        return UUID(str(value))
    except ValueError:
        return catalog_id(db, Ubicacion, value)


def employee_id(db):
    employee = db.scalar(select(Empleado).where(Empleado.nombre_completo == 'Custodio de prueba'))
    if not employee:
        employee = Empleado(nombre_completo='Custodio de prueba', is_active=True)
        db.add(employee)
        db.flush()
    return employee.id


def technician_id(db, name='Técnico de prueba', proveedor_id=None):
    technician = db.scalar(select(Tecnico).where(Tecnico.nombre_completo == name))
    if not technician:
        technician = Tecnico(nombre_completo=name, is_active=True, proveedor_id=proveedor_id, es_externo=proveedor_id is not None)
        db.add(technician)
        db.flush()
    return technician.id
