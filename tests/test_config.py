from pangeo_forge_orchestrator.config import get_config, get_fastapi_config


def test_get_config():
    c = get_config()
    for attr in ["fastapi", "github_app", "bakeries"]:
        assert hasattr(c, attr)


def test_get_fastapi_config():
    c = get_fastapi_config()
    for attr in ["github_app", "bakeries"]:
        assert not hasattr(c, attr)
    for attr in ["ADMIN_API_KEY_SHA256", "ENCRYPTION_SALT", "PANGEO_FORGE_API_KEY"]:
        assert hasattr(c, attr)
