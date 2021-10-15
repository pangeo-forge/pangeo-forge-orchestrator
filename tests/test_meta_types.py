import fsspec
import yaml

from pangeo_forge_orchestrator.meta_types.bakery import BakeryMeta


def test_bakery_meta(mock_github_http_server):
    _, _, bakery_meta_http_path = mock_github_http_server
    with fsspec.open(bakery_meta_http_path) as f:
        