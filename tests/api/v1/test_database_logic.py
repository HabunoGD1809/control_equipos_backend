import pytest
import asyncio
from httpx import AsyncClient
# CORRECCIÓN: Importar timezone para crear datetimes "aware"
from datetime import datetime, timedelta, timezone 
from uuid import uuid4

from app.models import Equipo, EstadoEquipo
from sqlalchemy.orm import Session
from sqlalchemy import text

pytestmark = pytest.mark.asyncio


async def test_trigger_updated_at_on_equipment_update(
    client: AsyncClient,
    db: Session,
    auth_token_admin: str,
    test_equipo_reservable: Equipo,
):
    """
    Verifica que el trigger 'trg_update_equipo_updated_at' actualiza el campo 'updated_at'.
    """
    admin_headers = {"Authorization": f"Bearer {auth_token_admin}"}
    equipo_id = test_equipo_reservable.id

    # === CORRECCIÓN FINAL Y DEFINITIVA ===
    # Usamos datetime.now(timezone.utc) en lugar de utcnow() para crear un datetime "aware".
    valor_antiguo = datetime.now(timezone.utc) - timedelta(seconds=10)
    
    db.execute(
        text("UPDATE control_equipos.equipos SET updated_at = :valor WHERE id = :id"),
        {"valor": valor_antiguo, "id": equipo_id}
    )
    db.commit()

    # Ahora ejecutamos la actualización a través de la API
    update_data = {"notas": f"Actualización final para trigger test {datetime.now()}"}
    response_update = await client.put(
        f"/api/v1/equipos/{equipo_id}", json=update_data, headers=admin_headers
    )
    assert response_update.status_code == 200, f"La actualización del equipo falló: {response_update.text}"

    # Obtenemos el nuevo valor directamente desde la BD
    resultado = db.execute(text("SELECT updated_at FROM control_equipos.equipos WHERE id = :id"), {'id': equipo_id})
    final_updated_at = resultado.scalar_one()

    # Ahora ambos datetimes son "aware" y se pueden comparar
    assert final_updated_at > valor_antiguo, (
        f"'updated_at' no se actualizó correctamente por el trigger. "
        f"Esperado: > {valor_antiguo}, Obtenido: {final_updated_at}"
    )


async def test_trigger_full_text_search_vector_creation(
    client: AsyncClient, auth_token_admin: str, test_estado_disponible: EstadoEquipo
):
    """
    Verifica que el trigger de búsqueda de texto completo genera el vector.
    """
    admin_headers = {"Authorization": f"Bearer {auth_token_admin}"}
    termino_unico_marca = f"NvidiaTest-{uuid4().hex[:6]}"
    create_data = {
        "nombre": "Servidor de Búsqueda Global",
        "numero_serie": f"TST-{uuid4().hex[:4].upper()}-{uuid4().hex[:4].upper()}",
        "estado_id": str(test_estado_disponible.id),
        "marca": termino_unico_marca,
    }

    response_create = await client.post("/api/v1/equipos/", json=create_data, headers=admin_headers)
    assert response_create.status_code == 201
    equipo_id = response_create.json()["id"]

    response_search = await client.get(
        f"/api/v1/equipos/search/global?q={termino_unico_marca}", headers=admin_headers
    )
    assert response_search.status_code == 200
    assert any(r["id"] == equipo_id for r in response_search.json())
