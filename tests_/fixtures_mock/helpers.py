import hashlib
import hmac
import json
from typing import Literal, Optional, TypedDict

import httpx

from ..fixture_models import GitHubWebhook


def add_hash_signature(request: GitHubWebhook, webhook_secret: str) -> GitHubWebhook:
    if request["headers"]["X-GitHub-Event"] != "dataflow":
        payload_bytes = bytes(json.dumps(request["payload"]), "utf-8")
    else:
        # special case for dataflow payload, to replicate how it is actually sent.
        # see comment in `pangeo_forge_orchestrator.routers.github_app::receive_github_hook`
        # for further detail. ideally, this special casing wll be removed eventually.
        payload_bytes = request["payload"].encode("utf-8")  # type: ignore

    hash_signature = hmac.new(
        bytes(webhook_secret, encoding="utf-8"),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()
    request["headers"].update({"X-Hub-Signature-256": f"sha256={hash_signature}"})
    return request


class MockHttpResponses(TypedDict, total=False):
    GET: Optional[httpx.Response]
    POST: Optional[httpx.Response]
    PATCH: Optional[httpx.Response]
    PUT: Optional[httpx.Response]
    DELETE: Optional[httpx.Response]


HttpMethod = Literal["GET", "POST", "PATCH", "PUT", "DELETE"]


def make_mock_httpx_client(mock_responses: dict[str, MockHttpResponses]):
    async def handler(request: httpx.Request):
        method: HttpMethod = request.method
        return mock_responses[request.url.path][method]

    mounts = {"https://api.github.com": httpx.MockTransport(handler)}

    return httpx.AsyncClient(mounts=mounts)
