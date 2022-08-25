import json
import os
import sys

import requests  # type: ignore

from pangeo_forge_orchestrator.routers.github_app import get_jwt

if __name__ == "__main__":
    deployment, webhook_url = sys.argv[1:3]

    env_deployment = os.environ.get("PANGEO_FORGE_DEPLOYMENT", "local")
    if deployment != env_deployment:
        raise ValueError(
            f"Mismatch between arg {deployment = } and {os.environ['PANGEO_FORGE_DEPLOYMENT'] = }"
        )

    jwt = get_jwt()

    # See https://docs.github.com/en/rest/apps/webhooks#update-a-webhook-configuration-for-an-app
    response = requests.patch(
        "https://api.github.com/app/hook/config",
        headers={
            "Authorization": f"bearer {jwt}",
            "Accept": "application/vnd.github+json",
        },
        data=json.dumps({"url": webhook_url}),
    )
    response.raise_for_status()
    print(response.status_code, response.text)
