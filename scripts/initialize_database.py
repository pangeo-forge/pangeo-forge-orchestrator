import json
import sys

import requests  # type: ignore

from pangeo_forge_orchestrator.config import get_config

c = get_config()

if __name__ == "__main__":
    # `app_address` might be http://localhost:8000 for a local instance, or e.g.
    #   https://pangeo-forge-api-pr-80.herokuapp.com for a review app instance.
    # `spec` is the full name of a mock feedstock, e.g. `cisaacstern/mock-dataset-feedstock`;
    #   the repo indicated by this spec must actually exist on GitHub.
    app_address, spec = sys.argv[1:3]
    headers = {
        "X-API-Key": c.fastapi.PANGEO_FORGE_API_KEY,
        "accept": "application/json",
        "Content-Type": "application/json",
    }
    feedstock_response = requests.post(
        f"{app_address}/feedstocks/",
        headers=headers,
        data=json.dumps({"spec": spec}),
    )
    feedstock_response.raise_for_status()
    bakery_response = requests.post(
        f"{app_address}/bakeries/",
        headers=headers,
        data=json.dumps(
            {
                "name": "local-test-bakery",
                "description": "A great bakery.",
                "region": "local",
            },
        ),
    )
    bakery_response.raise_for_status()
