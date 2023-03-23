import pytest


@pytest.mark.asyncio
async def test_receive_synchronize_request(recipe_pr):
    # get check runs at head_sha
    # httpx.get("/repos/{owner}/{repo}/commits/{ref}/check-runs")

    {
        "total_count": 1,
        "check_runs": [
            {
                "name": "Parse meta.yaml",
                "head_sha": recipe_pr["head_sha"],
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
