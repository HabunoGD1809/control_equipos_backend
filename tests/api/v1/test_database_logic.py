import pytest
import asyncio
from httpx import AsyncClient
from datetime import datetime
from uuid import uuid4
from typing import Generator

from app.models import Equipo, EstadoEquipo
from sqlalchemy.orm import Session, sessionmaker
from app.db.session import engine
from app.api import deps
from fastapi import FastAPI

pytestmark = pytest.mark.asyncio

# Creamos un Sessionmaker exclusivo para este archivo.
# Lo usaremos para crear sesiones 100% independientes y controladas.
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db_override_for_api_calls() -> Generator[Session, None, None]:
    """
    Generador de dependencias que proporciona una sesión de BD completamente nueva.
    Se asegura de que la operación de la API se confirme (commit) al finalizar.
    """
    db_session = TestSessionLocal()
    try:
        yield db_session
        db_session.commit()
    except Exception:
        db_session.rollback()
        raise
    finally:
        db_session.close()

@pytest.fixture(scope="function")
def test_equipo_para_trigger() -> Generator[Equipo, None, None]:
    """
    Fixture que crea y limpia un equipo usando su propia sesión y commit.
    Esto asegura que el dato existe y es visible para la API.
    """
    db_setup = TestSessionLocal()
    equipo_creado = None
    try:
        # Dependencia: Crear el estado si no existe.
        estado = db_setup.query(EstadoEquipo).filter(EstadoEquipo.nombre == "Disponible").first()
        if not estado:
            estado = EstadoEquipo(nombre="Disponible")
            db_setup.add(estado)
            db_setup.commit()
            db_setup.refresh(estado)

        # --- CORRECCIÓN CLAVE ---
        # Convertimos los caracteres del UUID a mayúsculas para cumplir
        # con la restricción de la base de datos.
        numero_serie_generado = f"TRIG-{uuid4().hex[:4].upper()}-{uuid4().hex[:4].upper()}"

        equipo_creado = Equipo(
            id=uuid4(),
            nombre="Equipo para Test de Trigger",
            numero_serie=numero_serie_generado,
            estado_id=estado.id
        )
        db_setup.add(equipo_creado)
        db_setup.commit()
        db_setup.refresh(equipo_creado)
        yield equipo_creado
    finally:
        if equipo_creado:
            equipo_a_borrar = db_setup.get(Equipo, equipo_creado.id)
            if equipo_a_borrar:
                db_setup.delete(equipo_a_borrar)
                db_setup.commit()
        db_setup.close()


async def test_trigger_updated_at_on_equipment_update(
    app: FastAPI,
    client: AsyncClient, 
    auth_token_admin: str, 
    test_equipo_para_trigger: Equipo
):
    """
    Verifica que el trigger 'trg_update_equipo_updated_at' actualiza el campo 'updated_at'.
    """
    admin_headers = {"Authorization": f"Bearer {auth_token_admin}"}
    equipo_id = test_equipo_para_trigger.id
    initial_updated_at = test_equipo_para_trigger.updated_at

    await asyncio.sleep(1.1)

    app.dependency_overrides[deps.get_db] = get_db_override_for_api_calls
    
    try:
        update_data = {"notas": f"Actualización trigger {datetime.now()}"}
        response_update = await client.put(f"/api/v1/equipos/{equipo_id}", json=update_data, headers=admin_headers)
        assert response_update.status_code == 200, f"La actualización falló: {response_update.text}"
    finally:
        app.dependency_overrides.pop(deps.get_db, None)

    with TestSessionLocal() as db_verify:
        equipo_refrescado = db_verify.get(Equipo, equipo_id)
        assert equipo_refrescado is not None, "No se pudo encontrar el equipo en la BD con una sesión nueva."
        final_updated_at = equipo_refrescado.updated_at

    assert final_updated_at > initial_updated_at, \
        f"'updated_at' no se actualizó. Inicial: {initial_updated_at}, Final: {final_updated_at}"


async def test_trigger_full_text_search_vector_creation(
    app: FastAPI,
    client: AsyncClient, 
    auth_token_admin: str,
    test_estado_disponible: EstadoEquipo
):
    """
    Verifica que el trigger de búsqueda de texto completo genera el vector
    correctamente al crear y actualizar un equipo.
    """
    admin_headers = {"Authorization": f"Bearer {auth_token_admin}"}
    
    termino_unico_marca = f"NvidiaTest-{uuid4().hex[:6]}"
    termino_unico_modelo = f"DGX-H100-Test-{uuid4().hex[:6]}"
    termino_unico_notas = f"ProcesadorQuanticoExperimental-{uuid4().hex[:6]}"

    create_data = {
        "nombre": "Servidor de Búsqueda Global",
        "numero_serie": f"TST-{uuid4().hex[:4].upper()}-{uuid4().hex[:4].upper()}",
        "estado_id": str(test_estado_disponible.id),
        "marca": termino_unico_marca,
        "modelo": termino_unico_modelo,
        "notas": f"Contiene un {termino_unico_notas}"
    }

    app.dependency_overrides[deps.get_db] = get_db_override_for_api_calls
    
    equipo_id = None
    try:
        response_create = await client.post("/api/v1/equipos/", json=create_data, headers=admin_headers)
        assert response_create.status_code == 201
        created_equipo_data = response_create.json()
        equipo_id = created_equipo_data["id"]

        for term in [termino_unico_marca, termino_unico_modelo, termino_unico_notas]:
            response_search = await client.get(f"/api/v1/equipos/search/global?q={term}", headers=admin_headers)
            assert response_search.status_code == 200
            search_results = response_search.json()
            assert len(search_results) >= 1
            assert any(r['id'] == equipo_id for r in search_results)
    finally:
        app.dependency_overrides.pop(deps.get_db, None)
        if equipo_id:
            with TestSessionLocal() as db_cleanup:
                equipo_a_borrar = db_cleanup.get(Equipo, equipo_id)
                if equipo_a_borrar:
                    db_cleanup.delete(equipo_a_borrar)
                    db_cleanup.commit()
