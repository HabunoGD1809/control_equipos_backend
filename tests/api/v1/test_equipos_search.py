import pytest
from httpx import AsyncClient
from fastapi import status

from app.core.config import settings
from app.models.equipo import Equipo

pytestmark = pytest.mark.asyncio

@pytest.mark.asyncio
async def test_search_equipos(
    client: AsyncClient, auth_token_supervisor: str, test_equipo_principal: Equipo
):
    """Prueba la búsqueda específica de equipos."""
    headers = {"Authorization": f"Bearer {auth_token_supervisor}"}
    search_term = test_equipo_principal.nombre.split(" ")[0]

    response = await client.get(
        f"{settings.API_V1_STR}/equipos/search",
        headers=headers,
        params={"q": search_term}
    )
    assert response.status_code == status.HTTP_200_OK, f"Detalle del error: {response.text}"
    results = response.json()
    assert isinstance(results, list)
    assert len(results) > 0, "La búsqueda no debería devolver una lista vacía para un término válido"
    assert any(str(test_equipo_principal.id) == item["id"] for item in results)
    assert "relevancia" in results[0]

@pytest.mark.asyncio
async def test_search_global(
    client: AsyncClient, auth_token_supervisor: str, test_equipo_principal: Equipo
):
    """Prueba la búsqueda global."""
    headers = {"Authorization": f"Bearer {auth_token_supervisor}"}
    search_term = test_equipo_principal.numero_serie.split("-")[1]

    response = await client.get(
        f"{settings.API_V1_STR}/equipos/search/global",
        headers=headers,
        params={"q": search_term}
    )
    assert response.status_code == status.HTTP_200_OK, f"Detalle del error: {response.text}"
    results = response.json()
    assert isinstance(results, list)
    assert len(results) > 0, "La búsqueda global no debería ser vacía"
    found = any(item["tipo"] == "equipo" and item["id"] == str(test_equipo_principal.id) for item in results)
    assert found, "El equipo de prueba no se encontró en la búsqueda global."
    assert "relevancia" in results[0]
    assert "metadata" in results[0]

@pytest.mark.asyncio
async def test_search_no_results(client: AsyncClient, auth_token_supervisor: str):
    """Prueba una búsqueda que no debería arrojar resultados."""
    headers = {"Authorization": f"Bearer {auth_token_supervisor}"}
    search_term = "TerminoInexistenteXYZ123"

    response = await client.get(
        f"{settings.API_V1_STR}/equipos/search",
        headers=headers,
        params={"q": search_term}
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == []
