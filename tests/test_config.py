from pangeo_forge_orchestrator.config import get_config


def test_get_config():
    c = get_config()
    for attr in ["github_app", "bakeries"]:
        assert hasattr(c, attr)
