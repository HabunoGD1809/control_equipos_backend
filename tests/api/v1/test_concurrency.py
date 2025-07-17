# import pytest
# import asyncio
# from httpx import AsyncClient
# from uuid import uuid4
# from datetime import datetime, timedelta, timezone

# from app.models import Equipo, EstadoEquipo
# from app.schemas.enums import TipoMovimientoEquipoEnum

# pytestmark = pytest.mark.asyncio

# @pytest.mark.asyncio
# async def test_concurrent_movements_on_same_item(
#     client: AsyncClient,
#     auth_token_admin: str,
#     auth_token_supervisor: str,
#     test_estado_disponible: EstadoEquipo,
# ):
#     """
#     Prueba que dos movimientos concurrentes sobre el mismo equipo resulten en
#     un éxito y un conflicto.
#     """
#     admin_headers = {"Authorization": f"Bearer {auth_token_admin}"}
#     supervisor_headers = {"Authorization": f"Bearer {auth_token_supervisor}"}

#     # Creamos un equipo único para esta prueba para evitar interferencias
#     equipo_data = {
#         "nombre": f"Equipo Concurrencia Movimiento {uuid4().hex[:4]}",
#         "numero_serie": f"CON-MOV-{uuid4().hex[:6].upper()}",
#         "estado_id": str(test_estado_disponible.id),
#         "ubicacion_actual": "Almacén Central Test"
#     }
#     response_create = await client.post("/api/v1/equipos/", headers=admin_headers, json=equipo_data)
#     assert response_create.status_code == 201
#     equipo_id = response_create.json()["id"]

#     mov_data = {
#         "equipo_id": equipo_id,
#         "tipo_movimiento": TipoMovimientoEquipoEnum.ASIGNACION_INTERNA.value,
#         "origen": equipo_data["ubicacion_actual"],
#         "proposito": "Asignación concurrente",
#     }

#     # Ejecutamos las dos tareas concurrentes
#     task1 = client.post("/api/v1/movimientos/", headers=admin_headers, json={**mov_data, "destino": "Destino A"})
#     task2 = client.post("/api/v1/movimientos/", headers=supervisor_headers, json={**mov_data, "destino": "Destino B"})
    
#     responses = await asyncio.gather(task1, task2)
#     status_codes = sorted([r.status_code for r in responses])

#     # Con la función de BD corregida, una debería tener éxito (201) y la otra debería
#     # ser rechazada por la lógica (400) porque el estado ya no es 'Disponible'.
#     assert status_codes == [201, 400], f"Se esperaban los códigos [201, 400] pero se obtuvieron {status_codes}"


# @pytest.mark.asyncio
# async def test_concurrent_reservations_fail(
#     client: AsyncClient,
#     auth_token_admin: str,
#     test_equipo_reservable: Equipo,
# ):
#     """
#     Prueba que dos reservas concurrentes para el mismo equipo/horario resulten en
#     un éxito (201) y un conflicto (409).
#     """
#     headers = {"Authorization": f"Bearer {auth_token_admin}"}
#     ahora = datetime.now(timezone.utc)
#     reserva_data = {
#         "equipo_id": str(test_equipo_reservable.id),
#         "fecha_hora_inicio": (ahora + timedelta(hours=1)).isoformat(),
#         "fecha_hora_fin": (ahora + timedelta(hours=2)).isoformat(),
#         "proposito": "Reserva concurrente final",
#     }

#     # Ejecutamos las tareas concurrentes
#     task1 = client.post("/api/v1/reservas/", headers=headers, json=reserva_data)
#     task2 = client.post("/api/v1/reservas/", headers=headers, json=reserva_data)

#     responses = await asyncio.gather(task1, task2)
#     status_codes = sorted([r.status_code for r in responses])

#     # Con la API de reservas corregida, la restricción EXCLUDE de la BD
#     # causará un IntegrityError, que la API debe convertir a 409.
#     assert status_codes == [201, 409], f"Se esperaban los códigos [201, 409] pero se obtuvieron {status_codes}"
