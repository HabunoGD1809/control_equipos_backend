import pytest
from httpx import AsyncClient
from fastapi import status
from uuid import uuid4
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.core.config import settings
from app.models import Equipo, InventarioStock, TipoItemInventario, LicenciaSoftware, AsignacionLicencia, Usuario
from app.schemas.enums import TipoMovimientoInvEnum
from sqlalchemy.orm import Session

pytestmark = pytest.mark.asyncio

@pytest.mark.asyncio
async def test_trigger_actualizar_inventario_stock(
    client: AsyncClient,
    auth_token_admin: str,
    db: Session,
    stock_inicial_toner: InventarioStock
):
    """
    Prueba que el trigger 'actualizar_inventario_stock_fn' funciona correctamente.
    Verifica que una entrada y una salida modifican el stock como se espera.
    """
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    tipo_item_id = stock_inicial_toner.tipo_item_id
    ubicacion = stock_inicial_toner.ubicacion
    
    db.refresh(stock_inicial_toner)
    stock_inicial_cantidad = stock_inicial_toner.cantidad_actual
    
    # 1. Realizar una ENTRADA
    cantidad_entrada = 5
    costo_entrada = Decimal("30.00")
    entrada_data = {
        "tipo_item_id": str(tipo_item_id),
        "tipo_movimiento": TipoMovimientoInvEnum.ENTRADA_COMPRA.value,
        "cantidad": cantidad_entrada,
        "ubicacion_destino": ubicacion,
        "costo_unitario": float(costo_entrada)
    }
    response_entrada = await client.post(f"{settings.API_V1_STR}/inventario/movimientos/", headers=headers, json=entrada_data)
    assert response_entrada.status_code == status.HTTP_201_CREATED, "La entrada de stock falló"

    db.refresh(stock_inicial_toner)
    assert stock_inicial_toner.cantidad_actual == stock_inicial_cantidad + cantidad_entrada, "El stock no se incrementó tras la entrada."
    
    # 2. Realizar una SALIDA
    cantidad_salida = 2
    salida_data = {
        "tipo_item_id": str(tipo_item_id),
        "tipo_movimiento": TipoMovimientoInvEnum.SALIDA_USO.value,
        "cantidad": cantidad_salida,
        "ubicacion_origen": ubicacion,
    }
    response_salida = await client.post(f"{settings.API_V1_STR}/inventario/movimientos/", headers=headers, json=salida_data)
    assert response_salida.status_code == status.HTTP_201_CREATED, "La salida de stock falló"

    db.refresh(stock_inicial_toner)
    assert stock_inicial_toner.cantidad_actual == stock_inicial_cantidad + cantidad_entrada - cantidad_salida, "El cálculo final de stock es incorrecto"

@pytest.mark.asyncio
async def test_trigger_licencia_disponible(
    client: AsyncClient,
    db: Session,
    auth_token_admin: str,
    licencia_office_disponible: LicenciaSoftware,
    equipo_sin_licencia: Equipo
):
    """
    Prueba que el trigger 'actualizar_licencia_disponible_fn' decrementa y
    incrementa la cantidad disponible de licencias correctamente.
    """
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    licencia_id = licencia_office_disponible.id
    
    # Obtener el estado inicial de la licencia desde la BD
    licencia_db = db.get(LicenciaSoftware, licencia_id)
    
    assert licencia_db is not None, f"La licencia con ID {licencia_id} no fue encontrada en la BD."
    
    cantidad_inicial = licencia_db.cantidad_disponible

    # 1. Asignar licencia
    asignacion_data = {"licencia_id": str(licencia_id), "equipo_id": str(equipo_sin_licencia.id)}
    response_asignar = await client.post(f"{settings.API_V1_STR}/licencias/asignaciones/", headers=headers, json=asignacion_data)
    assert response_asignar.status_code == status.HTTP_201_CREATED
    asignacion_id = response_asignar.json()["id"]

    # Verificar que la disponibilidad bajó
    db.refresh(licencia_db)
    assert licencia_db.cantidad_disponible == cantidad_inicial - 1, "La disponibilidad no decrementó tras asignar"

    # 2. Liberar (eliminar) asignación
    response_liberar = await client.delete(f"{settings.API_V1_STR}/licencias/asignaciones/{asignacion_id}", headers=headers)
    assert response_liberar.status_code == status.HTTP_200_OK

    # Verificar que la disponibilidad volvió a la inicial
    db.refresh(licencia_db)
    assert licencia_db.cantidad_disponible == cantidad_inicial, "La disponibilidad no incrementó tras liberar la licencia"
