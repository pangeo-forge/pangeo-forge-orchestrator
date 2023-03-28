import pytest

from .fixture_models import FixturedGitHubEvent


@pytest.mark.asyncio
async def test_handle_pr_synchronize_or_opened_event(recipe_pr: FixturedGitHubEvent):
    await recipe_pr.trigger()

    check_runs = await recipe_pr.pytest_http_client.get(
        "https://api.github.com/repos/"
        f"{recipe_pr.github_webhook['payload']['pull_request']['base']['repo']['full_name']}"
        f"/commits/{recipe_pr.github_webhook['payload']['pull_request']['head']['sha']}/check-runs"
    )
    assert check_runs.json() == {
        "total_count": 1,
        "check_runs": [
            {
                "name": "Parse meta.yaml",
                "head_sha": recipe_pr.github_webhook["payload"]["pull_request"]["head"]["sha"],
                "status": "completed",
                "started_at": "2022-08-11T21:22:51Z",
                "output": {
                    "title": "Recipe runs queued for latest commit",
                    "summary": "",
                },
                "details_url": "https://pangeo-forge.org/",
                "id": 0,
                "conclusion": "success",
                "completed_at": "2022-08-11T21:22:51Z",
            }
        ],
    }
