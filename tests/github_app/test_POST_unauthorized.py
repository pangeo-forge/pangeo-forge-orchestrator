import json
import os

import pytest


@pytest.mark.parametrize(
    "hash_signature_problem,expected_response_detail",
    [
        ("missing", "Request does not include a GitHub hash signature header."),
        ("incorrect", "Request hash signature invalid."),
    ],
)
@pytest.mark.asyncio
async def test_receive_github_hook_unauthorized(
    async_app_client,
    hash_signature_problem,
    expected_response_detail,
):
    if hash_signature_problem == "missing":
        headers = {}
    elif hash_signature_problem == "incorrect":
        os.environ["GITHUB_WEBHOOK_SECRET"] = "foobar"
        headers = {"X-Hub-Signature-256": "abcdefg"}

    response = await async_app_client.post(
        "/github/hooks/",
        json={},
        headers=headers,
    )
    assert response.status_code == 401
    assert json.loads(response.text)["detail"] == expected_response_detail
