from pangeo_forge_orchestrator.client import Client
from pangeo_forge_orchestrator.models import HeroCreate


def test_create_hero(http_server, create_request):

    client = Client(base_url=http_server)
    response = client.create_hero(hero=HeroCreate(**create_request))
    data = response.json()

    assert response.status_code == 200
    assert data["name"] == create_request["name"]
    assert data["secret_name"] == create_request["secret_name"]
    assert data["age"] is None
    assert data["id"] is not None
