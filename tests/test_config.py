from pangeo_forge_orchestrator.configurables.deployment import get_deployment
from pangeo_forge_orchestrator.configurables.github_app import GitHubApp


def test_get_config():
    c = get_deployment()
    for attr in [
        "name",
        "spawner",
        "dont_leak",
        "fastapi",
        "registered_runner_configs",
        "bakeries",
    ]:
        assert hasattr(c, attr)

    for attr in ["PANGEO_FORGE_API_KEY"]:
        assert hasattr(c.fastapi, attr)

    github_app = get_deployment(configurable=GitHubApp)
    for attr in ["app_name", "id", "private_key", "webhook_secret"]:
        assert hasattr(github_app, attr)
