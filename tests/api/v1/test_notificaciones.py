from datetime import datetime, timezone
import pytest
from httpx import AsyncClient
from uuid import uuid4, UUID
from fastapi import status
from fastapi.encoders import jsonable_encoder

from app.core.config import settings
from app.models.usuario import Usuario
from app.models.notificacion import Notificacion
from app.schemas.notificacion import NotificacionUpdate

from sqlalchemy.orm import Session

# Marcar todos los tests en este módulo para usar asyncio
pytestmark = pytest.mark.asyncio

async def test_read_notificaciones_success(
    client: AsyncClient, auth_token_usuario_regular: str, test_notificacion_user: Notificacion
):
    """Prueba listar las notificaciones del usuario actual."""
    headers = {"Authorization": f"Bearer {auth_token_usuario_regular}"}
    response = await client.get(f"{settings.API_V1_STR}/notificaciones/", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    notificaciones = response.json()
    assert isinstance(notificaciones, list)
    # Debería haber al menos la notificación de la fixture
    assert any(n["id"] == str(test_notificacion_user.id) for n in notificaciones)
    # Verificar que todas son del usuario actual (implícito por la consulta)

async def test_read_notificaciones_solo_no_leidas(
    client: AsyncClient, auth_token_usuario_regular: str, test_notificacion_user: Notificacion, db: Session
):
    """Prueba listar solo notificaciones no leídas."""
    headers = {"Authorization": f"Bearer {auth_token_usuario_regular}"}
    # Crear una notificación leída adicional para el mismo usuario
    notif_leida = Notificacion(usuario_id=test_notificacion_user.usuario_id, mensaje="Notif Leida", leido=True)
    db.add(notif_leida); db.flush(); db.refresh(notif_leida)

    # Listar solo no leídas
    response = await client.get(f"{settings.API_V1_STR}/notificaciones/", headers=headers, params={"solo_no_leidas": "true"})
    assert response.status_code == status.HTTP_200_OK
    notificaciones = response.json()
    assert isinstance(notificaciones, list)
    # Verificar que la notificación leída NO está
    assert not any(n["id"] == str(notif_leida.id) for n in notificaciones)
    # Verificar que la notificación no leída (de la fixture) SÍ está
    assert any(n["id"] == str(test_notificacion_user.id) for n in notificaciones)
    assert all(n["leido"] is False for n in notificaciones)

async def test_read_unread_count_success(
    client: AsyncClient, auth_token_usuario_regular: str, test_notificacion_user: Notificacion, db: Session
):
    """Prueba contar notificaciones no leídas."""
    headers = {"Authorization": f"Bearer {auth_token_usuario_regular}"}
    # Añadir otra no leída
    notif_no_leida2 = Notificacion(usuario_id=test_notificacion_user.usuario_id, mensaje="Otra no leida", leido=False)
    db.add(notif_no_leida2); db.flush()

    response = await client.get(f"{settings.API_V1_STR}/notificaciones/count/unread", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    count_data = response.json()
    assert "unread_count" in count_data
    # Debe haber al menos 2 no leídas (fixture + la creada aquí)
    assert count_data["unread_count"] >= 2

async def test_mark_notification_read_success(
    client: AsyncClient, auth_token_usuario_regular: str, test_notificacion_user: Notificacion
):
    """Prueba marcar una notificación como leída."""
    headers = {"Authorization": f"Bearer {auth_token_usuario_regular}"}
    notif_id = test_notificacion_user.id
    assert test_notificacion_user.leido is False # Verificar estado inicial

    update_schema = NotificacionUpdate(leido=True)
    update_data = jsonable_encoder(update_schema)
    response = await client.put(f"{settings.API_V1_STR}/notificaciones/{notif_id}/marcar", headers=headers, json=update_data)

    assert response.status_code == status.HTTP_200_OK, f"Detalle error: {response.text}"
    updated_notif = response.json()
    assert updated_notif["id"] == str(notif_id)
    assert updated_notif["leido"] is True
    assert updated_notif["fecha_leido"] is not None

async def test_mark_notification_unread_success(
    client: AsyncClient, auth_token_usuario_regular: str, test_notificacion_user: Notificacion, db: Session
):
    """Prueba marcar una notificación leída como no leída."""
    headers = {"Authorization": f"Bearer {auth_token_usuario_regular}"}
    notif_id = test_notificacion_user.id
    # Marcarla como leída primero
    test_notificacion_user.leido = True; test_notificacion_user.fecha_leido = datetime.now(timezone.utc)
    db.add(test_notificacion_user); db.flush()

    update_schema = NotificacionUpdate(leido=False)
    update_data = jsonable_encoder(update_schema)
    response = await client.put(f"{settings.API_V1_STR}/notificaciones/{notif_id}/marcar", headers=headers, json=update_data)

    assert response.status_code == status.HTTP_200_OK
    updated_notif = response.json()
    assert updated_notif["id"] == str(notif_id)
    assert updated_notif["leido"] is False
    assert updated_notif["fecha_leido"] is None

async def test_mark_notification_other_user_fail(
    client: AsyncClient, auth_token_admin: str, test_notificacion_user: Notificacion
):
    """Prueba que un usuario (admin) no pueda marcar notificación de otro usuario."""
    headers = {"Authorization": f"Bearer {auth_token_admin}"} # Usar admin
    notif_id = test_notificacion_user.id # Notificación del usuario normal

    update_schema = NotificacionUpdate(leido=True)
    update_data = jsonable_encoder(update_schema)
    response = await client.put(f"{settings.API_V1_STR}/notificaciones/{notif_id}/marcar", headers=headers, json=update_data)

    assert response.status_code == status.HTTP_403_FORBIDDEN

async def test_mark_all_as_read_success(
    client: AsyncClient, auth_token_usuario_regular: str, test_notificacion_user: Notificacion, db: Session, test_usuario_regular_fixture: Usuario
):
    """Prueba marcar todas las notificaciones como leídas."""
    headers = {"Authorization": f"Bearer {auth_token_usuario_regular}"}
    # Crear otra no leída
    notif_no_leida2 = Notificacion(usuario_id=test_usuario_regular_fixture.id, mensaje="Marcar Todas", leido=False)
    db.add(notif_no_leida2); db.flush()

    # Verificar que hay al menos 2 no leídas
    count_resp_before = await client.get(f"{settings.API_V1_STR}/notificaciones/count/unread", headers=headers)
    assert count_resp_before.json()["unread_count"] >= 2

    # Marcar todas
    response = await client.post(f"{settings.API_V1_STR}/notificaciones/marcar-todas-leidas", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    # Verificar mensaje de respuesta (opcional)
    assert "marcada(s) como leída(s)" in response.json()["msg"]

    # Verificar que el contador ahora es 0
    count_resp_after = await client.get(f"{settings.API_V1_STR}/notificaciones/count/unread", headers=headers)
    assert count_resp_after.json()["unread_count"] == 0

async def test_delete_notification_success(
    client: AsyncClient, auth_token_usuario_regular: str, test_notificacion_user: Notificacion
):
    """Prueba eliminar una notificación propia."""
    headers = {"Authorization": f"Bearer {auth_token_usuario_regular}"}
    notif_id = test_notificacion_user.id

    delete_response = await client.delete(f"{settings.API_V1_STR}/notificaciones/{notif_id}", headers=headers)
    assert delete_response.status_code == status.HTTP_200_OK
    assert "eliminada" in delete_response.json()["msg"]

    # Verificar que ya no existe (listar y comprobar)
    list_response = await client.get(f"{settings.API_V1_STR}/notificaciones/", headers=headers)
    notificaciones = list_response.json()
    assert not any(n["id"] == str(notif_id) for n in notificaciones)

async def test_delete_notification_other_user_fail(
    client: AsyncClient, auth_token_admin: str, test_notificacion_user: Notificacion
):
    """Prueba que un usuario no pueda eliminar notificación de otro."""
    headers = {"Authorization": f"Bearer {auth_token_admin}"} # Usar admin
    notif_id = test_notificacion_user.id # Notificación del usuario normal

    delete_response = await client.delete(f"{settings.API_V1_STR}/notificaciones/{notif_id}", headers=headers)
    assert delete_response.status_code == status.HTTP_403_FORBIDDEN
