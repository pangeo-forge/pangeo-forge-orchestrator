from typing import TypedDict, Union

import httpx
from pydantic import BaseModel, Field


class GitHubWebhook(TypedDict):
    headers: dict
    payload: Union[str, dict]  # union because of dataflow payload edge case


class FixturedGitHubEvent(BaseModel):
    app_client: httpx.AsyncClient = Field(
        ...,
        description="Test client for the Pangeo Forge FastAPI app.",
    )
    github_webhook: dict = Field(
        ...,
        description="Webhook sent by GitHub to the Pangeo Forge FastAPI app in response to the event.",
    )
    pytest_http_client: httpx.AsyncClient = Field(
        ...,
        description="An http client to be used within the test functions for calling GitHub.",
    )

    async def trigger(self) -> None:
        """Trigger the event."""

        webhook_response = await self.app_client.post(
            "/github/hooks/",
            json=self.github_webhook["payload"],
            headers=self.github_webhook["headers"],
        )
        assert webhook_response.status_code == 202

    class Config:
        arbitrary_types_allowed = True
