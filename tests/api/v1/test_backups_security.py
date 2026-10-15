"""Backups can only be downloaded by administrators from private storage."""
import pytest
from app.api.routes import backup_log as routes
from app.models.backup_log import BackupLog

@pytest.mark.asyncio
async def test_backup_download_permissions_and_storage_boundary(client, db, auth_token_admin, auth_token_supervisor, tmp_path, monkeypatch):
    folder = tmp_path / 'private'
    folder.mkdir()
    monkeypatch.setattr(routes, 'BACKUP_DIR', folder)
    external = tmp_path / 'external.zip'
    external.write_bytes(b'private data')
    log = BackupLog(backup_status='Completado', file_path=str(external))
    db.add(log); db.commit()
    url = f'/api/v1/backups/logs/{log.id}/download'
    assert (await client.get(url, headers={'Authorization': 'Bearer '+auth_token_supervisor})).status_code == 403
    headers = {'Authorization': 'Bearer '+auth_token_admin}
    assert (await client.get(url, headers=headers)).status_code == 404
    allowed = folder / 'complete.zip'
    allowed.write_bytes(b'backup contents')
    log.file_path = str(allowed); db.commit()
    response = await client.get(url, headers=headers)
    assert response.status_code == 200 and response.content == b'backup contents'
    assert response.headers['cache-control'] == 'no-store'
    assert response.headers['x-content-type-options'] == 'nosniff'
    log.backup_status = 'En Proceso'; db.commit()
    assert (await client.get(url, headers=headers)).status_code == 404
