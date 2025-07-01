import pytest
from httpx import AsyncClient
from fastapi import status
from uuid import uuid4
from datetime import date

from app.core.config import settings
from app.models.licencia_software import LicenciaSoftware
from app.models.usuario import Usuario
from app.models.software_catalogo import SoftwareCatalogo
from sqlalchemy.orm import Session

pytestmark = pytest.mark.asyncio

@pytest.mark.asyncio
async def test_ciclo_completo_asignar_y_liberar_licencia(
    client: AsyncClient,
    db: Session,
    auth_token_supervisor: str,
    licencia_office_disponible: LicenciaSoftware,
    test_usuario_regular_fixture: Usuario
):
    """
    Prueba el ciclo completo:
    1. Verifica estado inicial.
    2. Asigna una licencia y verifica que la disponibilidad baja.
    3. Libera la licencia y verifica que la disponibilidad sube.
    """
    headers = {"Authorization": f"Bearer {auth_token_supervisor}"}
    licencia_id = licencia_office_disponible.id
    usuario_id = test_usuario_regular_fixture.id
    
    # 1. Verificar estado inicial (fixture `licencia_office_disponible` se crea con 5)
    lote_inicial = db.get(LicenciaSoftware, licencia_id)
    assert lote_inicial is not None, "El lote de licencias no se encontró en la BD."
    assert lote_inicial.cantidad_disponible == 5
    assert lote_inicial.cantidad_total == 5

    # 2. Asignar la licencia al usuario
    asignacion_data = {"licencia_id": str(licencia_id), "usuario_id": str(usuario_id)}
    response_asignar = await client.post(
        f"{settings.API_V1_STR}/licencias/asignaciones/",
        headers=headers,
        json=asignacion_data
    )
    assert response_asignar.status_code == status.HTTP_201_CREATED
    asignacion_creada_id = response_asignar.json()["id"]
    
    # Verificar que la disponibilidad bajó a 4
    db.expire(lote_inicial) # Forzar a SQLAlchemy a recargar el objeto desde la BD
    lote_despues_de_asignar = db.get(LicenciaSoftware, licencia_id) # CORREGIDO
    assert lote_despues_de_asignar is not None, "El lote no se encontró después de asignar."
    assert lote_despues_de_asignar.cantidad_disponible == 4

    # 3. Liberar (eliminar) la asignación
    response_liberar = await client.delete(
        f"{settings.API_V1_STR}/licencias/asignaciones/{asignacion_creada_id}",
        headers=headers
    )
    assert response_liberar.status_code == status.HTTP_200_OK
    
    # Verificar que la disponibilidad volvió a 5
    db.expire(lote_despues_de_asignar)
    lote_final = db.get(LicenciaSoftware, licencia_id) # CORREGIDO
    assert lote_final is not None, "El lote no se encontró después de liberar."
    assert lote_final.cantidad_disponible == 5

@pytest.mark.asyncio
async def test_asignar_licencia_sin_disponibilidad_falla(
    client: AsyncClient,
    db: Session,
    auth_token_supervisor: str,
    licencia_office_disponible: LicenciaSoftware,
    test_usuario_regular_fixture: Usuario
):
    """
    Prueba que el sistema previene asignar más licencias de las disponibles.
    """
    headers = {"Authorization": f"Bearer {auth_token_supervisor}"}
    licencia_id = licencia_office_disponible.id

    # Forzar la cantidad disponible a 0 en la BD para la prueba
    lote = db.get(LicenciaSoftware, licencia_id) # CORREGIDO
    assert lote is not None, "El lote de licencias para la prueba no fue encontrado."
    lote.cantidad_disponible = 0
    db.add(lote)
    db.commit()
    
    # Intentar asignar una licencia cuando no hay disponibles
    asignacion_data = {"licencia_id": str(licencia_id), "usuario_id": str(test_usuario_regular_fixture.id)}
    response = await client.post(
        f"{settings.API_V1_STR}/licencias/asignaciones/",
        headers=headers,
        json=asignacion_data
    )
    
    # El trigger en la BD debería fallar, resultando en un error de la API
    assert response.status_code == status.HTTP_409_CONFLICT
    error_detail = response.json().get("detail", "").lower()
    assert "no puede ser negativa" in error_detail or "no hay licencias disponibles" in error_detail
