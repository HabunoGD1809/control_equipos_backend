from decimal import Decimal
import pytest
from httpx import AsyncClient
from uuid import uuid4, UUID
from datetime import datetime, timedelta, timezone
from fastapi import status
from fastapi.encoders import jsonable_encoder

from app.core.config import settings
from app.models.equipo import Equipo
from app.models.tipo_mantenimiento import TipoMantenimiento
from app.models.proveedor import Proveedor
from app.models.mantenimiento import Mantenimiento
from app.schemas.mantenimiento import MantenimientoCreate, MantenimientoUpdate
from app.schemas.enums import EstadoMantenimientoEnum

from sqlalchemy.orm import Session

pytestmark = pytest.mark.asyncio

# --- Fixtures ---
@pytest.fixture(scope="function")
async def equipo_para_mantenimiento(db: Session, test_estado_disponible) -> Equipo:
    from tests.api.v1.test_equipos import generate_valid_serie
    serie = generate_valid_serie("MANT")
    equipo = Equipo(
        nombre=f"Equipo Mant {serie}",
        numero_serie=serie,
        estado_id=test_estado_disponible.id,
        marca="Test",
        modelo="Maint",
        codigo_interno=f"MNT-{serie}",
        valor_adquisicion=Decimal("0"),
        centro_costo="Test"
    )
    db.add(equipo); db.flush(); db.refresh(equipo)
    return equipo

@pytest.fixture(scope="function")
async def tipo_mantenimiento_preventivo(db: Session) -> TipoMantenimiento:
    tipo = db.query(TipoMantenimiento).filter(TipoMantenimiento.nombre == "Preventivo Test").first()
    if not tipo:
        tipo = TipoMantenimiento(
            nombre="Preventivo Test", es_preventivo=True, periodicidad_dias=90, descripcion="Test"
        )
        db.add(tipo); db.flush(); db.refresh(tipo)
    return tipo

@pytest.fixture(scope="function")
async def tipo_mantenimiento_correctivo(db: Session) -> TipoMantenimiento:
    tipo = db.query(TipoMantenimiento).filter(TipoMantenimiento.nombre == "Correctivo Test").first()
    if not tipo:
        tipo = TipoMantenimiento(nombre="Correctivo Test", es_preventivo=False, descripcion="Test")
        db.add(tipo); db.flush(); db.refresh(tipo)
    return tipo

@pytest.fixture(scope="function")
async def proveedor_servicio_externo(db: Session) -> Proveedor:
    prov = db.query(Proveedor).filter(Proveedor.nombre == "Servicios Externos Test").first()
    if not prov:
        prov = Proveedor(nombre="Servicios Externos Test", contacto="test@servicios.com", rnc=f"RNC{uuid4().hex[:8]}")
        db.add(prov); db.flush(); db.refresh(prov)
    return prov


# --- Tests Corregidos ---
async def test_create_mantenimiento_programado_success(
    client: AsyncClient, auth_token_supervisor: str,
    equipo_para_mantenimiento: Equipo,
    tipo_mantenimiento_preventivo: TipoMantenimiento
):
    headers = {"Authorization": f"Bearer {auth_token_supervisor}"}
    fecha_programada_obj = datetime.now(timezone.utc) + timedelta(days=15)
    
    mant_schema = MantenimientoCreate(
        equipo_id=equipo_para_mantenimiento.id,
        tipo_mantenimiento_id=tipo_mantenimiento_preventivo.id,
        fecha_programada=fecha_programada_obj,
        fecha_inicio=None,
        fecha_finalizacion=None,
        costo_estimado=Decimal("100.00"),
        costo_real=None,
        tecnico_responsable="Equipo Interno IT",
        proveedor_servicio_id=None,
        estado=EstadoMantenimientoEnum.PROGRAMADO,
        prioridad=1,
        observaciones="Mantenimiento preventivo anual programado"
    )
    data = jsonable_encoder(mant_schema)
    response = await client.post(f"{settings.API_V1_STR}/mantenimientos/", headers=headers, json=data)
    
    assert response.status_code == status.HTTP_201_CREATED, f"Detalle error: {response.text}"
    created_mant = response.json()
    assert created_mant["equipo_id"] == str(equipo_para_mantenimiento.id)
    assert created_mant["tipo_mantenimiento_id"] == str(tipo_mantenimiento_preventivo.id)
    assert created_mant["estado"] == "Programado"
    assert created_mant["tecnico_responsable"] == "Equipo Interno IT"
    assert "id" in created_mant

async def test_create_mantenimiento_completado_success(
    client: AsyncClient, auth_token_supervisor: str,
    equipo_para_mantenimiento: Equipo,
    tipo_mantenimiento_correctivo: TipoMantenimiento,
    proveedor_servicio_externo: Proveedor
):
    headers = {"Authorization": f"Bearer {auth_token_supervisor}"}
    fecha_inicio_obj = datetime.now(timezone.utc) - timedelta(days=2)
    fecha_fin_obj = datetime.now(timezone.utc) - timedelta(days=1)
    
    mant_schema = MantenimientoCreate(
        equipo_id=equipo_para_mantenimiento.id,
        tipo_mantenimiento_id=tipo_mantenimiento_correctivo.id,
        fecha_programada=None,
        fecha_inicio=fecha_inicio_obj,
        fecha_finalizacion=fecha_fin_obj,
        costo_estimado=Decimal("120.00"),
        costo_real=Decimal("150.75"),
        tecnico_responsable="Juan Pérez (Servicios Externos Test)",
        proveedor_servicio_id=proveedor_servicio_externo.id,
        estado=EstadoMantenimientoEnum.COMPLETADO,
        prioridad=2,
        observaciones="Se reemplazó fuente de poder."
    )
    data = jsonable_encoder(mant_schema)
    response = await client.post(f"{settings.API_V1_STR}/mantenimientos/", headers=headers, json=data)
    
    assert response.status_code == status.HTTP_201_CREATED, f"Detalle error: {response.text}"
    created_mant = response.json()
    assert created_mant["estado"] == "Completado"
    assert Decimal(created_mant["costo_real"]) == Decimal("150.75")
    assert created_mant["proveedor_servicio_id"] == str(proveedor_servicio_externo.id)
    assert created_mant["fecha_proximo_mantenimiento"] is None

async def test_create_mantenimiento_calcula_proximo(
     client: AsyncClient, auth_token_supervisor: str,
     equipo_para_mantenimiento: Equipo,
     tipo_mantenimiento_preventivo: TipoMantenimiento
):
    headers = {"Authorization": f"Bearer {auth_token_supervisor}"}
    fecha_fin_dt = datetime.fromisoformat("2025-04-15T10:00:00+00:00")
    fecha_esperada_proximo = fecha_fin_dt + timedelta(days=90)

    mant_schema = MantenimientoCreate(
        equipo_id=equipo_para_mantenimiento.id,
        tipo_mantenimiento_id=tipo_mantenimiento_preventivo.id,
        fecha_programada=None,
        fecha_inicio=None,
        fecha_finalizacion=fecha_fin_dt,
        costo_estimado=Decimal("50.00"),
        costo_real=Decimal("45.00"),
        tecnico_responsable="Test Calc",
        proveedor_servicio_id=None,
        estado=EstadoMantenimientoEnum.COMPLETADO,
        prioridad=0,
        observaciones="Test de cálculo"
    )
    data = jsonable_encoder(mant_schema)
    response = await client.post(f"{settings.API_V1_STR}/mantenimientos/", headers=headers, json=data)
    
    assert response.status_code == status.HTTP_201_CREATED
    created_mant = response.json()
    assert created_mant["fecha_proximo_mantenimiento"] is not None
    fecha_proximo_recibida = datetime.fromisoformat(created_mant["fecha_proximo_mantenimiento"])
    assert abs(fecha_proximo_recibida - fecha_esperada_proximo) < timedelta(seconds=1)

async def test_create_mantenimiento_no_permission(
    client: AsyncClient, auth_token_user: str,
    equipo_para_mantenimiento: Equipo,
    tipo_mantenimiento_correctivo: TipoMantenimiento
):
    headers = {"Authorization": f"Bearer {auth_token_user}"}
    
    mant_schema = MantenimientoCreate(
        equipo_id=equipo_para_mantenimiento.id,
        tipo_mantenimiento_id=tipo_mantenimiento_correctivo.id,
        tecnico_responsable="No Permitido",
        fecha_programada=datetime.now(timezone.utc) + timedelta(days=1),
        fecha_inicio=None,
        fecha_finalizacion=None,
        costo_estimado=Decimal("0.0"),
        costo_real=None,
        proveedor_servicio_id=None,
        estado=EstadoMantenimientoEnum.PROGRAMADO,
        prioridad=0,
        observaciones="Intento sin permiso"
    )
    data = jsonable_encoder(mant_schema)
    response = await client.post(f"{settings.API_V1_STR}/mantenimientos/", headers=headers, json=data)
    assert response.status_code == status.HTTP_403_FORBIDDEN

async def test_read_mantenimientos_success(
    client: AsyncClient, auth_token_supervisor: str,
    equipo_para_mantenimiento: Equipo,
    tipo_mantenimiento_correctivo: TipoMantenimiento
):
    headers = {"Authorization": f"Bearer {auth_token_supervisor}"}
    
    mant_schema = MantenimientoCreate(
        equipo_id=equipo_para_mantenimiento.id,
        tipo_mantenimiento_id=tipo_mantenimiento_correctivo.id,
        tecnico_responsable="List Test",
        fecha_programada=datetime.now(timezone.utc) + timedelta(days=2),
        fecha_inicio=None,
        fecha_finalizacion=None,
        costo_estimado=Decimal("0"),
        costo_real=None,
        proveedor_servicio_id=None,
        estado=EstadoMantenimientoEnum.PROGRAMADO,
        prioridad=0,
        observaciones="Mantenimiento para listar"
    )
    data = jsonable_encoder(mant_schema)
    create_resp = await client.post(f"{settings.API_V1_STR}/mantenimientos/", headers=headers, json=data)
    assert create_resp.status_code == status.HTTP_201_CREATED

    response = await client.get(f"{settings.API_V1_STR}/mantenimientos/", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    mantenimientos = response.json()
    assert isinstance(mantenimientos, list)
    assert len(mantenimientos) > 0

async def test_read_mantenimientos_filter_by_equipo(
    client: AsyncClient, auth_token_supervisor: str,
    equipo_para_mantenimiento: Equipo,
    tipo_mantenimiento_correctivo: TipoMantenimiento
):
    headers = {"Authorization": f"Bearer {auth_token_supervisor}"}
    
    mant_schema = MantenimientoCreate(
        equipo_id=equipo_para_mantenimiento.id,
        tipo_mantenimiento_id=tipo_mantenimiento_correctivo.id,
        tecnico_responsable="Filter Test",
        fecha_programada=datetime.now(timezone.utc) + timedelta(days=3),
        fecha_inicio=None,
        fecha_finalizacion=None,
        costo_estimado=Decimal("0"),
        costo_real=None,
        proveedor_servicio_id=None,
        estado=EstadoMantenimientoEnum.PROGRAMADO,
        prioridad=0,
        observaciones="Mantenimiento para filtrar"
    )
    data = jsonable_encoder(mant_schema)
    create_resp = await client.post(f"{settings.API_V1_STR}/mantenimientos/", headers=headers, json=data)
    assert create_resp.status_code == status.HTTP_201_CREATED
    mant_id = create_resp.json()["id"]

    response = await client.get(f"{settings.API_V1_STR}/mantenimientos/", headers=headers, params={"equipo_id": str(equipo_para_mantenimiento.id)})
    assert response.status_code == status.HTTP_200_OK
    mantenimientos = response.json()
    assert isinstance(mantenimientos, list)
    assert len(mantenimientos) > 0
    assert all(m["equipo_id"] == str(equipo_para_mantenimiento.id) for m in mantenimientos)
    assert any(m["id"] == mant_id for m in mantenimientos)

async def test_read_mantenimiento_by_id_success(
    client: AsyncClient, auth_token_supervisor: str,
    equipo_para_mantenimiento: Equipo,
    tipo_mantenimiento_correctivo: TipoMantenimiento
):
    headers = {"Authorization": f"Bearer {auth_token_supervisor}"}
    
    mant_schema = MantenimientoCreate(
        equipo_id=equipo_para_mantenimiento.id,
        tipo_mantenimiento_id=tipo_mantenimiento_correctivo.id,
        tecnico_responsable="Get By ID Test",
        fecha_programada=None,
        fecha_inicio=None,
        fecha_finalizacion=None,
        costo_estimado=Decimal("1.0"),
        costo_real=None,
        proveedor_servicio_id=None,
        estado=EstadoMantenimientoEnum.PROGRAMADO,
        prioridad=1,
        observaciones="Mantenimiento para leer por ID"
    )
    data = jsonable_encoder(mant_schema)
    create_resp = await client.post(f"{settings.API_V1_STR}/mantenimientos/", headers=headers, json=data)
    assert create_resp.status_code == status.HTTP_201_CREATED
    mant_id = create_resp.json()["id"]

    response = await client.get(f"{settings.API_V1_STR}/mantenimientos/{mant_id}", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    mant_data = response.json()
    assert mant_data["id"] == mant_id
    assert mant_data["tecnico_responsable"] == "Get By ID Test"

async def test_update_mantenimiento_success(
     client: AsyncClient, auth_token_supervisor: str,
     equipo_para_mantenimiento: Equipo,
     tipo_mantenimiento_preventivo: TipoMantenimiento
):
    headers = {"Authorization": f"Bearer {auth_token_supervisor}"}
    
    create_schema = MantenimientoCreate(
        equipo_id=equipo_para_mantenimiento.id,
        tipo_mantenimiento_id=tipo_mantenimiento_preventivo.id,
        fecha_programada=datetime.now(timezone.utc) + timedelta(days=5),
        fecha_inicio=None,
        fecha_finalizacion=None,
        costo_estimado=Decimal("100.00"),
        costo_real=None,
        tecnico_responsable="Inicial",
        proveedor_servicio_id=None,
        estado=EstadoMantenimientoEnum.PROGRAMADO,
        prioridad=1,
        observaciones="Mantenimiento para actualizar"
    )
    create_data = jsonable_encoder(create_schema)
    create_resp = await client.post(f"{settings.API_V1_STR}/mantenimientos/", headers=headers, json=create_data)
    assert create_resp.status_code == status.HTTP_201_CREATED
    mant_creado = create_resp.json()
    mant_id = mant_creado["id"]

    # CORRECCIÓN: Se mantiene el valor de 'prioridad' si no se va a cambiar.
    update_schema_1 = MantenimientoUpdate(
        estado=EstadoMantenimientoEnum.EN_PROCESO,
        fecha_inicio=datetime.now(timezone.utc),
        costo_estimado=None,
        costo_real=None,
        prioridad=mant_creado["prioridad"] # <-- CORRECCIÓN
    )
    update_data_1 = jsonable_encoder(update_schema_1.model_dump(exclude_unset=True))
    update_resp_1 = await client.put(f"{settings.API_V1_STR}/mantenimientos/{mant_id}", headers=headers, json=update_data_1)
    assert update_resp_1.status_code == status.HTTP_200_OK, f"Detalle error: {update_resp_1.text}"
    assert update_resp_1.json()["estado"] == "En Proceso"

    # CORRECCIÓN: Igual que en la corrección anterior.
    update_schema_2 = MantenimientoUpdate(
        estado=EstadoMantenimientoEnum.COMPLETADO,
        fecha_finalizacion=datetime.now(timezone.utc) + timedelta(hours=1),
        costo_estimado=None,
        costo_real=Decimal("50.0"),
        observaciones="Todo OK",
        prioridad=mant_creado["prioridad"] # <-- CORRECCIÓN
    )
    update_data_2 = jsonable_encoder(update_schema_2.model_dump(exclude_unset=True))
    update_resp_2 = await client.put(f"{settings.API_V1_STR}/mantenimientos/{mant_id}", headers=headers, json=update_data_2)
    assert update_resp_2.status_code == status.HTTP_200_OK, f"Detalle error: {update_resp_2.text}"
    updated_mant = update_resp_2.json()
    assert updated_mant["estado"] == "Completado"
    assert Decimal(updated_mant["costo_real"]) == Decimal("50.00")
    assert updated_mant["observaciones"] == "Todo OK"
    assert updated_mant["fecha_proximo_mantenimiento"] is not None

async def test_delete_mantenimiento_success(
     client: AsyncClient, auth_token_admin: str,
     equipo_para_mantenimiento: Equipo,
     tipo_mantenimiento_correctivo: TipoMantenimiento
):
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    
    mant_schema = MantenimientoCreate(
        equipo_id=equipo_para_mantenimiento.id,
        tipo_mantenimiento_id=tipo_mantenimiento_correctivo.id,
        tecnico_responsable="Delete Test",
        fecha_programada=datetime.now(timezone.utc) + timedelta(days=1),
        fecha_inicio=None,
        fecha_finalizacion=None,
        costo_estimado=Decimal("0"),
        costo_real=None,
        proveedor_servicio_id=None,
        estado=EstadoMantenimientoEnum.PROGRAMADO,
        prioridad=0,
        observaciones="Mantenimiento para eliminar"
    )
    data = jsonable_encoder(mant_schema)
    create_resp = await client.post(f"{settings.API_V1_STR}/mantenimientos/", headers=headers, json=data)
    assert create_resp.status_code == status.HTTP_201_CREATED
    mant_id = create_resp.json()["id"]

    delete_response = await client.delete(f"{settings.API_V1_STR}/mantenimientos/{mant_id}", headers=headers)
    assert delete_response.status_code == status.HTTP_200_OK
    assert "eliminado correctamente" in delete_response.json()["msg"]

    get_response = await client.get(f"{settings.API_V1_STR}/mantenimientos/{mant_id}", headers=headers)
    assert get_response.status_code == status.HTTP_404_NOT_FOUND
