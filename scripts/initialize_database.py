import json
import sys

import requests  # type: ignore

from pangeo_forge_orchestrator.config import get_config

c = get_config()

if __name__ == "__main__":
    port, spec = sys.argv[1:3]
    headers = {
        "X-API-Key": c.fastapi.PANGEO_FORGE_API_KEY,
        "accept": "application/json",
        "Content-Type": "application/json",
    }
    feedstock_response = requests.post(
        f"http://localhost:{port}/feedstocks/",
        headers=headers,
        data=json.dumps({"spec": spec}),
    )
    feedstock_response.raise_for_status()
    bakery_response = requests.post(
        f"http://localhost:{port}/bakeries/",
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
