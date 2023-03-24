import httpx
import pytest


@pytest.mark.asyncio
async def test_handle_pr_synchronize_or_opened_event(recipe_pr: tuple[dict, httpx.AsyncClient]):
    pr, http_client = recipe_pr
    check_runs = await http_client.get(
        "https://api.github.com"
        f"/repos/{pr['base_repo_full_name']}/commits/{pr['head_sha']}/check-runs"
    )
    assert check_runs.json() == {
        "total_count": 1,
        "check_runs": [
            {
                "name": "Parse meta.yaml",
                "head_sha": pr["head_sha"],
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
