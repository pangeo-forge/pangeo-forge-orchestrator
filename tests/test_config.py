from pangeo_forge_orchestrator.configurables import Deployment, FastAPI, GitHubApp, get_configurable


def test_get_config(api_key):
    c = get_configurable(configurable=Deployment)
    for attr in [
        "name",
        "spawner",
        "dont_leak",
        "registered_runner_configs",
        "bakeries",
    ]:
        assert hasattr(c, attr)

    fastapi = get_configurable(configurable=FastAPI)
    assert hasattr(fastapi, "key")
    assert fastapi.key == api_key

    github_app = get_configurable(configurable=GitHubApp)
    for attr in ["app_name", "id", "private_key", "webhook_secret"]:
        assert hasattr(github_app, attr)

    secret_vals = [fastapi.key, github_app.private_key, github_app.webhook_secret]
    for sv in secret_vals:
        assert repr(sv) == "*****"
        assert str(sv) == "*****"
