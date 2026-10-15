import io
import pytest
from PIL import Image
from app.api.routes import empresa as routes

pytestmark = pytest.mark.asyncio

async def test_company_private_fields_validation_and_public_projection(client, auth_token_admin):
    headers = {'Authorization': 'Bearer '+auth_token_admin}
    previous = await client.get('/api/v1/empresa/', headers=headers)
    assert previous.status_code == 200
    previous_logo = previous.json()['logo_url']
    response = await client.put('/api/v1/empresa/', json={'nombre': '  Empresa UX  ', 'telefono': '123', 'email': 'contacto@example.com'}, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()['nombre'] == 'Empresa UX'
    assert response.json()['updated_at']
    public = await client.get('/api/v1/empresa/publica')
    assert response.json()['logo_url'] == previous_logo
    assert public.json() == {'nombre': 'Empresa UX', 'logo_url': previous_logo}
    assert (await client.put('/api/v1/empresa/', json={'nombre': '   '}, headers=headers)).status_code == 422
    assert (await client.put('/api/v1/empresa/', json={'nombre': 'Empresa', 'email': 'inválido'}, headers=headers)).status_code == 422

async def test_company_is_private_for_users_without_permission(client, auth_token_usuario_regular):
    headers = {'Authorization': 'Bearer '+auth_token_usuario_regular}
    assert (await client.get('/api/v1/empresa/', headers=headers)).status_code == 403
    assert (await client.put('/api/v1/empresa/', json={'nombre': 'Cambio'}, headers=headers)).status_code == 403

async def test_logo_replacement_preserves_company_and_removes_previous_file(client, auth_token_admin, monkeypatch, tmp_path):
    monkeypatch.setattr(routes, 'LOGO_DIR', tmp_path)
    headers = {'Authorization': 'Bearer '+auth_token_admin}
    assert (await client.put('/api/v1/empresa/', json={'nombre': 'Empresa con logo', 'telefono': '123'}, headers=headers)).status_code == 200
    for color in ['red', 'blue']:
        buffer = io.BytesIO(); Image.new('RGB', (120, 60), color).save(buffer, 'PNG')
        response = await client.post('/api/v1/empresa/logo', files={'file': ('logo.png', buffer.getvalue(), 'image/png')}, headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()['nombre'] == 'Empresa con logo' and response.json()['telefono'] == '123'
        assert len(list(tmp_path.glob('*.png'))) == 1
    public = await client.get('/api/v1/empresa/publica/logo')
    assert public.status_code == 200 and public.headers['content-type'] == 'image/png'
    with Image.open(io.BytesIO(public.content)) as image:
        assert image.getpixel((0, 0))[:3] == (0, 0, 255)
    assert (await client.delete('/api/v1/empresa/logo', headers=headers)).status_code == 200
    assert list(tmp_path.glob('*.png')) == []
    assert (await client.get('/api/v1/empresa/publica/logo')).status_code == 404

async def test_logo_rejects_invalid_and_oversized_images(client, auth_token_admin, monkeypatch, tmp_path):
    monkeypatch.setattr(routes, 'LOGO_DIR', tmp_path)
    headers = {'Authorization': 'Bearer '+auth_token_admin}
    invalid = await client.post('/api/v1/empresa/logo', files={'file': ('logo.svg', b'<svg></svg>', 'image/svg+xml')}, headers=headers)
    assert invalid.status_code == 415
    oversized = await client.post('/api/v1/empresa/logo', files={'file': ('large.png', b'x'*(2*1024*1024+1), 'image/png')}, headers=headers)
    assert oversized.status_code == 413
    assert not list(tmp_path.iterdir())

@pytest.mark.parametrize('color', ['Negro', 'Cian', 'Magenta', 'Amarillo', 'Tricolor', 'Otro'])
async def test_selected_toner_color_is_persisted(client, auth_token_admin, color):
    headers = {'Authorization': 'Bearer '+auth_token_admin}
    response = await client.post('/api/v1/inventario/tipos/', json={'nombre': 'Tóner UX '+color, 'categoria': 'Consumible', 'unidad_medida': 'Unidad', 'tecnologia': 'Tóner', 'color': color, 'stock_minimo': 0}, headers=headers)
    assert response.status_code == 201, response.text
    saved = await client.get('/api/v1/inventario/tipos/'+response.json()['id'], headers=headers)
    assert saved.status_code == 200 and saved.json()['color'] == color
