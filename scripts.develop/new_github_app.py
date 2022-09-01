import http.server
import json
import os
import socketserver
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests  # type: ignore
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
CACHEDIR = REPO_ROOT / ".github_app_manifest_flow"
AUTHORIZE = "authorize.html"
REDIRECT = "redirect.html"
PORT = 3000
AUTHORIZE_URL = f"http://localhost:{PORT}/{AUTHORIZE}"
PLACEHOLDER_HOOK_URL = "https://example.com/github/events"
TEST_ORG = "pforgetest"

if not os.path.exists(CACHEDIR):
    os.mkdir(CACHEDIR)


def get_app_name_and_desc(github_username, deployment, pr_number=None):
    """For a given github_username and deployment type, return a name and description for the app.
    Names are determined as follows:
      - `prod` deployment is always named `pangeo-forge`.
      - `staging` deployment is always named `pangeo-forge-staging`.
      - `review` deployment is named `pforge-pr-{pr_number}` where pr_number is the number of the
        PR on `pangeo-forge-orchestrator` from which the review app is deployed.
      - `local` deployment is named `pforge-local-{github_username}`. This deployment is for the
        named developer's personal use, and is run via a proxy to their local machine.
    """

    if deployment in ("prod", "staging"):
        github_app_name = "pangeo-forge"  # the name of the production app
        desc = "The official pangeo-forge github app."
        if deployment == "staging":
            github_app_name += "-staging"
            desc = desc.replace("The", "A staging deployment of the")
    else:
        desc = "A development version of the pangeo-forge github app."
        if deployment == "review":
            github_app_name = f"pforge-pr-{pr_number}"
        elif deployment == "local":
            github_app_name = f"pforge-local-{github_username}"

    return github_app_name, desc


def main(github_username, deployment, pr_number=None):

    app_name, description = get_app_name_and_desc(github_username, deployment, pr_number=pr_number)

    # We're going to serve from the `CACHEDIR` as base,
    # so the redirect page will be at this address
    redirect_url = f"http://localhost:{PORT}/{REDIRECT}"

    # For manifest parameters docs, see:
    # https://docs.github.com/en/developers/apps/building-github-apps/creating-a-github-app-from-a-manifest#github-app-manifest-parameters
    manifest = dict(
        name=app_name,
        url="https://pangeo-forge.org/",  # TODO: Specify this?
        # NOTE: The hook url is deliberately given as a placeholder here. The real hook url will be
        # set in a subsequent step. See ``docs/development_guide.md`` for details.
        hook_attributes={"url": PLACEHOLDER_HOOK_URL},
        redirect_url=redirect_url,
        callback_urls=["https://example.com/callback"],  # TODO: Customize this.
        description=description,
        public=False,
        default_events=[
            "issue_comment",
            "pull_request",
        ],
        default_permissions={  # TODO: See if these can be pruned
            "administration": "write",
            "checks": "write",
            "contents": "write",
            "deployments": "write",
            "issues": "read",
            "metadata": "read",
            "pull_requests": "write",
        },
    )

    # This page content adapted from official GitHub docs, here:
    # https://docs.github.com/en/developers/apps/building-github-apps/creating-a-github-app-from-a-manifest#examples
    org = "pangeo-forge" if deployment in ("prod", "staging") else TEST_ORG
    content = f"""
    <html>
        <form
         action="https://github.com/organizations/{org}/settings/apps/new?state=abc123"
         method="post">
            Create a GitHub App from Manifest: <input type="text" name="manifest" id="manifest"><br>
            <input type="submit" value="Submit">
        </form>
        <script>
            input = document.getElementById("manifest")
            input.value = JSON.stringify({json.dumps(manifest)})
        </script>
    <html>
    """

    with open(f"{CACHEDIR}/{AUTHORIZE}", "w") as f:
        f.write(content)

    return app_name, org


if __name__ == "__main__":

    user_token = os.environ.get("GITHUB_PAT", None)
    if not user_token:
        raise ValueError("Env variable 'GITHUB_PAT' required, but unset.")

    args = sys.argv[1:]
    # args should be passed as GITHUB_USERNAME, DEPLOYMENT then [optionally] PR_NUMBER
    # it would be more robust to enforce/document this with argparse or similar, but moving
    # quickly now for a the first draft.
    deployment = args[1]
    allowed_deployments = ("prod", "staging", "review", "local")
    if deployment not in allowed_deployments:
        raise ValueError(f"{deployment =} not in {allowed_deployments =}.")

    pr_number = args[2] if len(args) == 3 else None
    if deployment == "review" and not pr_number:
        raise ValueError("PR number must be given for review app.")

    app_name, org = main(*sys.argv[1:])

    creds_outpath = REPO_ROOT / f"secrets/config.{app_name}.yaml"
    if os.path.exists(creds_outpath):
        raise ValueError(f"{creds_outpath} already exists. Delete this file to continue.")

    # Write the redirect page to disk
    with open(f"{CACHEDIR}/{REDIRECT}", "w") as f:
        f.write(f"<html>Authorization complete! Creds stored in <b>{creds_outpath}</b></html>")

    print(f"Create new app with {app_name=}, {deployment=}, {org=}?\nInput 'yes' to continue.")
    yes = input()
    if yes != "yes":
        sys.exit()

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=CACHEDIR, **kwargs)

        def do_GET(self):
            p = urlparse(self.path)
            if "code" in p.query and p.path == f"/{REDIRECT}":
                # For docs on exchanging temporary code for app config, see:
                # https://docs.github.com/en/developers/apps/building-github-apps/creating-a-github-app-from-a-manifest#3-you-exchange-the-temporary-code-to-retrieve-the-app-configuration
                code = parse_qs(p.query)["code"][0]
                response = requests.post(
                    f"https://api.github.com/app-manifests/{code}/conversions",
                    headers={
                        "Authorization": f"token {user_token}",
                        "Accept": "application/vnd.github+json",
                    },
                )
                response.raise_for_status()
                response_json = response.json()
                app_config = {
                    "id": response_json["id"],
                    "app_name": app_name,
                    "webhook_secret": response_json["webhook_secret"],
                    "private_key": response_json["pem"],
                }
                if os.path.exists(creds_outpath):
                    with open(creds_outpath) as c:
                        creds = yaml.safe_load(c)
                else:
                    creds = {}
                with open(creds_outpath, "w") as f:
                    creds["github_app"] = app_config
                    yaml.dump(creds, f)

            return http.server.SimpleHTTPRequestHandler.do_GET(self)

    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print("To authorize a new dev app, navigate to", AUTHORIZE_URL)
        httpd.serve_forever()
