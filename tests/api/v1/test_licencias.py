import pytest
from httpx import AsyncClient
from uuid import uuid4, UUID
from datetime import date, timedelta
from fastapi import status
from fastapi.encoders import jsonable_encoder
from decimal import Decimal
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.software_catalogo import SoftwareCatalogo
from app.models.licencia_software import LicenciaSoftware
from app.models.asignacion_licencia import AsignacionLicencia
from app.models.equipo import Equipo
from app.models.usuario import Usuario
from app.models.proveedor import Proveedor
from app.schemas.software_catalogo import SoftwareCatalogoCreate, SoftwareCatalogoUpdate
from app.schemas.licencia_software import LicenciaSoftwareCreate, LicenciaSoftwareUpdate
from app.schemas.asignacion_licencia import AsignacionLicenciaCreate

pytestmark = pytest.mark.asyncio

@pytest.fixture(scope="function")
async def software_office(db: Session) -> SoftwareCatalogo:
    sw = db.query(SoftwareCatalogo).filter(SoftwareCatalogo.nombre == "Microsoft Office Test").first()
    if not sw:
        sw = SoftwareCatalogo(
            nombre="Microsoft Office Test", version="2021", fabricante="Microsoft",
            categoria="Ofimática", tipo_licencia="Perpetua", metrica_licenciamiento="Por Dispositivo",
            descripcion="Suite ofimática"
        )
        db.add(sw); db.flush(); db.refresh(sw)
    return sw

@pytest.fixture(scope="function")
async def software_win(db: Session) -> SoftwareCatalogo:
    sw = db.query(SoftwareCatalogo).filter(SoftwareCatalogo.nombre == "Windows Test Pro").first()
    if not sw:
        sw = SoftwareCatalogo(
            nombre="Windows Test Pro", version="11", fabricante="Microsoft",
            categoria="Sistema Operativo", tipo_licencia="OEM", metrica_licenciamiento="Por Dispositivo",
            descripcion="Sistema Operativo"
        )
        db.add(sw); db.flush(); db.refresh(sw)
    return sw

@pytest.fixture(scope="function")
async def licencia_office_disponible(db: Session, software_office: SoftwareCatalogo, test_proveedor: Proveedor) -> LicenciaSoftware:
    lic = db.query(LicenciaSoftware).filter(LicenciaSoftware.software_catalogo_id == software_office.id, LicenciaSoftware.notas == "Fixture Test Office 5").first()
    if lic:
        db.query(AsignacionLicencia).filter(AsignacionLicencia.licencia_id == lic.id).delete()
        db.flush()
        lic.cantidad_disponible = lic.cantidad_total
        lic.fecha_adquisicion = date.today() - timedelta(days=30)
        db.add(lic)
    else:
        lic = LicenciaSoftware(
            software_catalogo_id=software_office.id,
            fecha_adquisicion=date.today() - timedelta(days=30),
            cantidad_total=5,
            cantidad_disponible=5,
            costo_adquisicion=Decimal("1000.00"),
            notas="Fixture Test Office 5",
            proveedor_id=test_proveedor.id
        )
        db.add(lic)
    db.commit() # Commit para asegurar que la fixture esté en la DB
    db.refresh(lic)
    return lic

@pytest.fixture(scope="function")
async def equipo_sin_licencia(db: Session, test_estado_disponible) -> Equipo:
    from tests.api.v1.test_equipos import generate_valid_serie
    serie = generate_valid_serie("LIC")
    equipo = Equipo(
        nombre=f"Equipo Lic {serie}",
        numero_serie=serie,
        estado_id=test_estado_disponible.id,
        marca="Test",
        modelo="Lic",
        codigo_interno=f"LIC-{serie}",
        valor_adquisicion=Decimal("0.0"),
        centro_costo="Test"
    )
    db.add(equipo); db.flush(); db.refresh(equipo)
    return equipo

# --- Tests ---

async def test_create_licencia_success(client: AsyncClient, auth_token_admin: str, software_win: SoftwareCatalogo, test_proveedor: Proveedor):
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    
    # CORRECCIÓN: Se añade el campo 'cantidad_disponible' explícitamente.
    lic_schema = LicenciaSoftwareCreate(
        software_catalogo_id=software_win.id,
        clave_producto=f"WINKEY-{uuid4().hex[:8]}",
        fecha_adquisicion=date.today(),
        fecha_expiracion=None,
        proveedor_id=test_proveedor.id,
        numero_orden_compra="OC-123",
        cantidad_total=1,
        cantidad_disponible=1,  # Corregido
        costo_adquisicion=Decimal("120.00"),
        notas="Licencia de Windows para test",
    )
    data = jsonable_encoder(lic_schema)
    response = await client.post(f"{settings.API_V1_STR}/licencias/", headers=headers, json=data)
    
    assert response.status_code == status.HTTP_201_CREATED, f"Detalle error: {response.text}"
    created_lic = response.json()
    assert created_lic["software_catalogo_id"] == str(software_win.id)
    assert created_lic["clave_producto"] == lic_schema.clave_producto
    assert created_lic["cantidad_total"] == 1
    assert created_lic["cantidad_disponible"] == 1
    assert "id" in created_lic

# (El resto del archivo no tenía los errores indicados, por lo que se mantiene igual)

async def test_create_software_catalogo_success(client: AsyncClient, auth_token_admin: str):
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    sw_name = f"Software Test {uuid4().hex[:6]}"
    sw_schema = SoftwareCatalogoCreate(
        nombre=sw_name, version="1.0", fabricante="Test Factory", categoria="Test",
        tipo_licencia="Suscripción Anual", metrica_licenciamiento="Por Usuario Nominal",
        descripcion="Software de prueba"
    )
    data = jsonable_encoder(sw_schema)
    response = await client.post(f"{settings.API_V1_STR}/licencias/catalogo/", headers=headers, json=data)
    assert response.status_code == status.HTTP_201_CREATED, f"Detalle error: {response.text}"
    created_sw = response.json()
    assert created_sw["nombre"] == sw_name
    assert created_sw["version"] == "1.0"
    assert "id" in created_sw

async def test_read_software_catalogo_success(client: AsyncClient, auth_token_user: str, software_office: SoftwareCatalogo):
    headers = {"Authorization": f"Bearer {auth_token_user}"}
    response = await client.get(f"{settings.API_V1_STR}/licencias/catalogo/", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    catalogo = response.json()
    assert isinstance(catalogo, list)
    assert len(catalogo) > 0
    assert any(sw["id"] == str(software_office.id) for sw in catalogo)

async def test_read_licencias_success(client: AsyncClient, auth_token_user: str, licencia_office_disponible: LicenciaSoftware):
    headers = {"Authorization": f"Bearer {auth_token_user}"}
    response = await client.get(f"{settings.API_V1_STR}/licencias/", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    licencias = response.json()
    assert isinstance(licencias, list)
    assert len(licencias) > 0
    assert any(lic["id"] == str(licencia_office_disponible.id) for lic in licencias)

async def test_update_licencia_success(client: AsyncClient, auth_token_admin: str, licencia_office_disponible: LicenciaSoftware):
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    new_exp_date = date.today() + timedelta(days=365)
    update_schema = LicenciaSoftwareUpdate(
        fecha_expiracion=new_exp_date,
        notas="Licencia de prueba actualizada",
        costo_adquisicion=Decimal("1150.00"),
        numero_orden_compra="OC-UPDATED"
    )
    update_data = jsonable_encoder(update_schema.model_dump(exclude_unset=True))
    response = await client.put(f"{settings.API_V1_STR}/licencias/{licencia_office_disponible.id}", headers=headers, json=update_data)
    assert response.status_code == status.HTTP_200_OK, f"Detalle error: {response.text}"
    updated_lic = response.json()
    assert updated_lic["id"] == str(licencia_office_disponible.id)
    assert updated_lic["fecha_expiracion"] == new_exp_date.isoformat()
    assert updated_lic["notas"] == "Licencia de prueba actualizada"

async def test_create_asignacion_equipo_success(
    client: AsyncClient, auth_token_admin: str,
    licencia_office_disponible: LicenciaSoftware,
    equipo_sin_licencia: Equipo,
    db: Session
):
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    lic_id = licencia_office_disponible.id
    equipo_id = equipo_sin_licencia.id
    
    db.refresh(licencia_office_disponible)
    disponibles_antes = licencia_office_disponible.cantidad_disponible

    asign_schema = AsignacionLicenciaCreate(
        licencia_id=lic_id,
        equipo_id=equipo_id,
        usuario_id=None,
        instalado=True,
        notas="Asignación a equipo"
    )
    data = jsonable_encoder(asign_schema)
    response = await client.post(f"{settings.API_V1_STR}/licencias/asignaciones/", headers=headers, json=data)
    assert response.status_code == status.HTTP_201_CREATED, f"Detalle error: {response.text}"
    created_asig = response.json()
    assert created_asig["licencia_id"] == str(lic_id)
    assert created_asig["equipo_id"] == str(equipo_id)
    assert created_asig["usuario_id"] is None
    assert "id" in created_asig

    lic_despues_resp = await client.get(f"{settings.API_V1_STR}/licencias/{lic_id}", headers=headers)
    lic_actualizada = lic_despues_resp.json()
    assert lic_actualizada["cantidad_disponible"] == disponibles_antes - 1

async def test_create_asignacion_usuario_success(
    client: AsyncClient, auth_token_admin: str,
    licencia_office_disponible: LicenciaSoftware,
    test_user: Usuario,
    db: Session
):
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    lic_id = licencia_office_disponible.id
    user_id = test_user.id
    
    db.refresh(licencia_office_disponible)
    disponibles_antes = licencia_office_disponible.cantidad_disponible

    asign_schema = AsignacionLicenciaCreate(
        licencia_id=lic_id,
        usuario_id=user_id,
        equipo_id=None,
        instalado=True,
        notas="Asignación a usuario"
    )
    data = jsonable_encoder(asign_schema)
    response = await client.post(f"{settings.API_V1_STR}/licencias/asignaciones/", headers=headers, json=data)
    assert response.status_code == status.HTTP_201_CREATED, f"Detalle error: {response.text}"
    created_asig = response.json()
    assert created_asig["licencia_id"] == str(lic_id)
    assert created_asig["usuario_id"] == str(user_id)
    assert created_asig["equipo_id"] is None

    lic_despues_resp = await client.get(f"{settings.API_V1_STR}/licencias/{lic_id}", headers=headers)
    lic_actualizada = lic_despues_resp.json()
    assert lic_actualizada["cantidad_disponible"] == disponibles_antes - 1

async def test_create_asignacion_no_disponible(
    client: AsyncClient, auth_token_admin: str,
    licencia_office_disponible: LicenciaSoftware,
    equipo_sin_licencia: Equipo,
    db: Session
):
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    
    licencia_office_disponible.cantidad_disponible = 0
    db.add(licencia_office_disponible)
    db.commit()

    asign_schema = AsignacionLicenciaCreate(
        licencia_id=licencia_office_disponible.id,
        equipo_id=equipo_sin_licencia.id,
        usuario_id=None,
        instalado=True,
        notas="Intento sin disponibilidad"
    )
    data = jsonable_encoder(asign_schema)
    response = await client.post(f"{settings.API_V1_STR}/licencias/asignaciones/", headers=headers, json=data)
    assert response.status_code == status.HTTP_409_CONFLICT
    assert "no hay licencias disponibles" in response.json()["detail"].lower()

async def test_create_asignacion_duplicada_equipo(
    client: AsyncClient, auth_token_admin: str,
    licencia_office_disponible: LicenciaSoftware,
    equipo_sin_licencia: Equipo
):
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    
    asign_schema1 = AsignacionLicenciaCreate(
        licencia_id=licencia_office_disponible.id,
        equipo_id=equipo_sin_licencia.id,
        usuario_id=None,
        instalado=True,
        notas="Primera"
    )
    data1 = jsonable_encoder(asign_schema1)
    response1 = await client.post(f"{settings.API_V1_STR}/licencias/asignaciones/", headers=headers, json=data1)
    assert response1.status_code == status.HTTP_201_CREATED

    asign_schema2 = AsignacionLicenciaCreate(
        licencia_id=licencia_office_disponible.id,
        equipo_id=equipo_sin_licencia.id,
        usuario_id=None,
        instalado=True,
        notas="Duplicada"
    )
    data2 = jsonable_encoder(asign_schema2)
    response2 = await client.post(f"{settings.API_V1_STR}/licencias/asignaciones/", headers=headers, json=data2)
    assert response2.status_code == status.HTTP_409_CONFLICT
    assert "ya está asignada a este equipo" in response2.json()["detail"].lower()

async def test_read_asignaciones_success(
    client: AsyncClient, auth_token_user: str,
    licencia_office_disponible: LicenciaSoftware,
    equipo_sin_licencia: Equipo,
    auth_token_admin: str,
    db: Session
):
    headers_admin = {"Authorization": f"Bearer {auth_token_admin}"}

    existing_asig = db.query(AsignacionLicencia).filter_by(licencia_id=licencia_office_disponible.id, equipo_id=equipo_sin_licencia.id).first()
    if not existing_asig:
        asign_schema = AsignacionLicenciaCreate(
            licencia_id=licencia_office_disponible.id,
            equipo_id=equipo_sin_licencia.id,
            usuario_id=None,
            instalado=True,
            notas="Para listar"
        )
        data = jsonable_encoder(asign_schema)
        await client.post(f"{settings.API_V1_STR}/licencias/asignaciones/", headers=headers_admin, json=data)

    headers_user = {"Authorization": f"Bearer {auth_token_user}"}
    response = await client.get(f"{settings.API_V1_STR}/licencias/asignaciones/", headers=headers_user)
    assert response.status_code == status.HTTP_200_OK
    asignaciones = response.json()
    assert isinstance(asignaciones, list)
    assert len(asignaciones) >= 1

async def test_delete_asignacion_success(
    client: AsyncClient, auth_token_admin: str,
    licencia_office_disponible: LicenciaSoftware,
    equipo_sin_licencia: Equipo,
    db: Session
):
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    lic_id = licencia_office_disponible.id
    equipo_id = equipo_sin_licencia.id

    db.refresh(licencia_office_disponible)
    disponibles_antes = licencia_office_disponible.cantidad_disponible

    # Asegurar que la asignación exista antes de intentar borrarla
    existing_asig = db.query(AsignacionLicencia).filter_by(licencia_id=lic_id, equipo_id=equipo_id).first()
    if not existing_asig:
        asign_schema = AsignacionLicenciaCreate(
            licencia_id=lic_id,
            equipo_id=equipo_id,
            usuario_id=None,
            instalado=True,
            notas="Para borrar"
        )
        data = jsonable_encoder(asign_schema)
        create_response = await client.post(f"{settings.API_V1_STR}/licencias/asignaciones/", headers=headers, json=data)
        assert create_response.status_code == status.HTTP_201_CREATED
        asignacion_id = create_response.json()["id"]
    else:
        asignacion_id = existing_asig.id

    db.refresh(licencia_office_disponible)
    disponibles_despues_de_crear = licencia_office_disponible.cantidad_disponible
    
    # Solo se debe haber reducido si se acaba de crear
    if not existing_asig:
        assert disponibles_despues_de_crear == disponibles_antes - 1

    delete_response = await client.delete(f"{settings.API_V1_STR}/licencias/asignaciones/{asignacion_id}", headers=headers)
    assert delete_response.status_code == status.HTTP_200_OK
    assert "eliminada correctamente" in delete_response.json()["msg"]

    get_response = await client.get(f"{settings.API_V1_STR}/licencias/asignaciones/{asignacion_id}", headers=headers)
    assert get_response.status_code == status.HTTP_404_NOT_FOUND

    db.refresh(licencia_office_disponible)
    assert licencia_office_disponible.cantidad_disponible == disponibles_antes
