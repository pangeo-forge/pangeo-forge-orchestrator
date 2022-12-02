from pangeo_forge_orchestrator.configurables import Deployment, GitHubApp, get_configurable


def test_get_config():
    c = get_configurable(configurable=Deployment)
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

    github_app = get_configurable(configurable=GitHubApp)
    for attr in ["app_name", "id", "private_key", "webhook_secret"]:
        assert hasattr(github_app, attr)
