import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
from uuid import uuid4
from datetime import datetime, timedelta, timezone
from typing import Generator

from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.models import Equipo, ReservaEquipo, EstadoEquipo
from app.schemas.enums import TipoMovimientoEquipoEnum
from app.api import deps


pytestmark = pytest.mark.asyncio


concurrency_engine = create_engine(
    str(settings.DATABASE_URI),
    isolation_level="SERIALIZABLE",
    poolclass=NullPool,
)
TestingSessionLocalForConcurrency = sessionmaker(
    autocommit=False, autoflush=False, bind=concurrency_engine
)

def get_db_override_for_concurrency() -> Generator[Session, None, None]:
    """
    Generador de dependencias que proporciona una sesión de BD con nivel SERIALIZABLE.
    Se asegura de que cada solicitud concurrente tenga su propia transacción aislada.
    """
    db_session = TestingSessionLocalForConcurrency()
    try:
        yield db_session
        db_session.commit()
    except Exception:
        db_session.rollback()
        raise
    finally:
        db_session.close()


@pytest.fixture(scope="function")
def equipo_para_concurrencia() -> Generator[Equipo, None, None]:
    """
    Crea un equipo único para pruebas de concurrencia.
    Usa su propia sesión SERIALIZABLE y hace commit para que el dato sea
    visible para las transacciones del test. También se auto-limpia.
    """
    db_setup = TestingSessionLocalForConcurrency()
    equipo_creado = None
    try:
        # Dependencia: Asegurar que el estado 'Disponible' y 'En Uso' existan y estén confirmados.
        for estado_nombre in ["Disponible", "En Uso"]:
            estado = db_setup.query(EstadoEquipo).filter(EstadoEquipo.nombre == estado_nombre).first()
            if not estado:
                estado = EstadoEquipo(nombre=estado_nombre)
                db_setup.add(estado)
                db_setup.commit()

        estado_disponible = db_setup.query(EstadoEquipo).filter(EstadoEquipo.nombre == "Disponible").one()
        
        numero_serie_generado = f"CONCUR-{uuid4().hex[:4].upper()}-{uuid4().hex[:4].upper()}"

        equipo_creado = Equipo(
            id=uuid4(),
            nombre=f"Equipo Concurrencia {uuid4().hex[:6]}",
            numero_serie=numero_serie_generado,
            estado_id=estado_disponible.id,
            ubicacion_actual="Almacén de Pruebas"
        )
        db_setup.add(equipo_creado)
        db_setup.commit()
        db_setup.refresh(equipo_creado)
        
        yield equipo_creado
    finally:
        if equipo_creado:
            db_cleanup = TestingSessionLocalForConcurrency()
            try:
                equipo_a_borrar = db_cleanup.get(Equipo, equipo_creado.id)
                if equipo_a_borrar:
                    db_cleanup.query(ReservaEquipo).filter(ReservaEquipo.equipo_id == equipo_a_borrar.id).delete(synchronize_session=False)
                    db_cleanup.delete(equipo_a_borrar)
                    db_cleanup.commit()
            finally:
                db_cleanup.close()
        db_setup.close()

async def test_concurrent_movements_on_same_item(
    app: FastAPI,
    auth_token_admin: str,
    auth_token_supervisor: str,
    equipo_para_concurrencia: Equipo,
):
    """
    Prueba que dos movimientos concurrentes sobre el mismo equipo resulten en
    un éxito (201) y un conflicto (409 o 500).
    """
    headers_admin = {"Authorization": f"Bearer {auth_token_admin}"}
    headers_supervisor = {"Authorization": f"Bearer {auth_token_supervisor}"}
    
    mov_data = {
        "equipo_id": str(equipo_para_concurrencia.id),
        "tipo_movimiento": TipoMovimientoEquipoEnum.ASIGNACION_INTERNA.value,
        "origen": equipo_para_concurrencia.ubicacion_actual,
        "proposito": "Asignación concurrente"
    }

    app.dependency_overrides[deps.get_db] = get_db_override_for_concurrency

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client1, \
                 AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client2:
            
            task_admin = asyncio.create_task(client1.post(f"{settings.API_V1_STR}/movimientos/", headers=headers_admin, json={**mov_data, "destino": "Admin"}))
            task_supervisor = asyncio.create_task(client2.post(f"{settings.API_V1_STR}/movimientos/", headers=headers_supervisor, json={**mov_data, "destino": "Supervisor"}))

            done, pending = await asyncio.wait([task_admin, task_supervisor], timeout=15.0)

            if pending:
                for task in pending:
                    task.cancel()
                pytest.fail("El test se colgó (deadlock probable). Timeout de 15 segundos excedido.")
            
            responses = [task.result() for task in done]

    finally:
        app.dependency_overrides.pop(deps.get_db, None)

    status_codes = sorted([r.status_code for r in responses])
    
    assert 201 in status_codes, "Se esperaba que al menos una operación tuviera éxito (201)."
    assert 409 in status_codes or 500 in status_codes, "Se esperaba que la otra operación fallara con 409 (Conflicto) o 500 (Error de Serialización)."


async def test_concurrent_reservations_fail(
    app: FastAPI,
    auth_token_admin: str,
    equipo_para_concurrencia: Equipo,
):
    """
    Prueba que dos reservas concurrentes para el mismo equipo/horario resulten en
    un éxito (201) y un conflicto (409).
    """
    headers = {"Authorization": f"Bearer {auth_token_admin}"}
    ahora = datetime.now(timezone.utc)
    reserva_data = {
        "equipo_id": str(equipo_para_concurrencia.id),
        "fecha_hora_inicio": (ahora + timedelta(hours=1)).isoformat(),
        "fecha_hora_fin": (ahora + timedelta(hours=2)).isoformat(),
        "proposito": "Reserva Concurrente"
    }

    app.dependency_overrides[deps.get_db] = get_db_override_for_concurrency

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client1, \
                 AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client2:

            task1 = asyncio.create_task(client1.post(f"{settings.API_V1_STR}/reservas/", headers=headers, json=reserva_data))
            task2 = asyncio.create_task(client2.post(f"{settings.API_V1_STR}/reservas/", headers=headers, json=reserva_data))
            
            done, pending = await asyncio.wait([task1, task2], timeout=15.0)

            if pending:
                for task in pending:
                    task.cancel()
                pytest.fail("El test de reservas se colgó (deadlock probable). Timeout de 15 segundos excedido.")
            
            responses = [task.result() for task in done]

    finally:
        app.dependency_overrides.pop(deps.get_db, None)

    status_codes = sorted([r.status_code for r in responses])
    
    assert status_codes == [201, 409], f"Se esperaban los códigos [201, 409] pero se obtuvieron {status_codes}"

    with TestingSessionLocalForConcurrency() as db_verify:
        reservas_creadas_count = db_verify.query(ReservaEquipo).filter_by(equipo_id=equipo_para_concurrencia.id).count()
        assert reservas_creadas_count == 1, f"Se esperaba 1 reserva en la BD, pero se encontraron {reservas_creadas_count}"

