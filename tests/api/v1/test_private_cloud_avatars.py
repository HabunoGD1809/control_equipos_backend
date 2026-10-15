import io
from unittest.mock import Mock
import pytest
from PIL import Image
from app.core import storage

pytestmark = pytest.mark.asyncio


async def test_cloud_photo_stays_private_and_is_downloaded_through_authenticated_route(client, auth_token_admin, monkeypatch):
    objects = {}
    cloud = Mock()
    def upload(stream, bucket, key, ExtraArgs):
        assert 'ACL' not in ExtraArgs
        objects[key] = stream.read()
    cloud.upload_fileobj.side_effect = upload
    cloud.get_object.side_effect = lambda **kwargs: {'Body': io.BytesIO(objects[kwargs['Key']])}
    monkeypatch.setattr(storage, 'get_s3_client', lambda: cloud)
    monkeypatch.setattr(storage.settings, 'AWS_BUCKET_NAME', 'private-avatar-test')
    picture = io.BytesIO()
    Image.new('RGB', (32, 32), (24, 96, 128)).save(picture, 'PNG')
    headers = {'Authorization': 'Bearer ' + auth_token_admin}
    response = await client.post('/api/v1/usuarios/me/avatar', headers=headers, files={'file': ('foto.png', picture.getvalue(), 'image/png')})
    assert response.status_code == 200
    url = response.json()['avatar_url']
    assert url.startswith('/api/v1/usuarios/avatar/') and '?v=' in url
    assert (await client.get(url)).status_code == 401
    assert cloud.get_object.call_count == 0
    downloaded = await client.get(url, headers=headers)
    assert downloaded.status_code == 200
    assert downloaded.headers['cache-control'] == 'private, no-store'
    assert downloaded.headers['content-type'].startswith('image/jpeg')
    assert downloaded.content == next(iter(objects.values()))
    assert cloud.close.call_count == 2


async def test_cloud_read_failure_is_a_controlled_unavailable_response(client, auth_token_admin, monkeypatch):
    cloud = Mock()
    cloud.get_object.side_effect = RuntimeError('Storage unavailable')
    monkeypatch.setattr(storage, 'get_s3_client', lambda: cloud)
    response = await client.get('/api/v1/usuarios/avatar/user_11111111-1111-4111-8111-111111111111.jpg', headers={'Authorization': 'Bearer ' + auth_token_admin})
    assert response.status_code == 503
    assert 'Storage unavailable' not in response.text
    cloud.close.assert_called_once()


async def test_cloud_read_has_a_size_limit_and_closes_the_stream(client, auth_token_admin, monkeypatch):
    stream = io.BytesIO(b'x' * (2 * 1024 * 1024 + 1))
    cloud = Mock(); cloud.get_object.return_value = {'Body': stream}
    monkeypatch.setattr(storage, 'get_s3_client', lambda: cloud)
    response = await client.get('/api/v1/usuarios/avatar/user_11111111-1111-4111-8111-111111111111.jpg', headers={'Authorization': 'Bearer ' + auth_token_admin})
    assert response.status_code == 413 and stream.closed
    cloud.close.assert_called_once()
