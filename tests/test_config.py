from pangeo_forge_orchestrator.configurables.deployment import get_deployment


def test_get_config():
    c = get_deployment()
    for attr in ["fastapi", "github_app", "bakeries"]:
        assert hasattr(c, attr)

    for attr in ["PANGEO_FORGE_API_KEY"]:
        assert hasattr(c.fastapi, attr)

    for attr in ["app_name", "id", "private_key", "webhook_secret"]:
        assert hasattr(c.github_app, attr)
