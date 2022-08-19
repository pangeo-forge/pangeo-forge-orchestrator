import http.server
import json
import os
import socketserver
import sys
from urllib.parse import parse_qs, urlparse

import requests  # type: ignore
import yaml

CACHEDIR = f"{os.getcwd()}/.github_app_manifest_flow"
AUTHORIZE = "authorize.html"
REDIRECT = "redirect.html"
PORT = 3000

if not os.path.exists(CACHEDIR):
    os.mkdir(CACHEDIR)


def main(smee_proxy_url):
    """ """

    # Write the redirect page to disk
    with open(f"{CACHEDIR}/{REDIRECT}", "w") as f:
        f.write("<html>You've been redirected</html>")

    # We're going to serve from the `CACHEDIR` as base,
    # so the redirect page will be at this address
    redirect_url = f"http://localhost:{PORT}/{REDIRECT}"

    p = urlparse(smee_proxy_url)
    abbreviated_smee_channel_id = p.path[1:8]
    proxy_url_without_scheme = p.netloc + p.path

    # For manifest parameters docs, see:
    # https://docs.github.com/en/developers/apps/building-github-apps/creating-a-github-app-from-a-manifest#github-app-manifest-parameters
    manifest = dict(
        name=f"pangeo-forge-dev-{abbreviated_smee_channel_id}",
        # TODO: Make this url actually work. This will *not* work with Smee, because IIUC Smee only
        # forwards incoming traffic. To make outgoing traffic queryable, I think we'll need to use
        # something like Ngrok instead. The reason I've chosen Smee is that you get a persistent
        # url (i.e. channel) for free. With Ngrok, a persistent url requires a paid plan.
        url=f"https://pangeo-forge.org/?orchestratorEndpoint={proxy_url_without_scheme}",
        hook_attributes={"url": smee_proxy_url},
        redirect_url=redirect_url,
        callback_urls=["https://example.com/callback"],  # TODO: customize
        description="A dev instance of the pangeo-forge github app.",
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
    content = f"""
    <html>
        <form action="https://github.com/settings/apps/new?state=abc123" method="post">
            Create a GitHub App Manifest: <input type="text" name="manifest" id="manifest"><br>
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

    return f"http://localhost:{PORT}/{AUTHORIZE}"


if __name__ == "__main__":

    user_token = os.environ.get("GITHUB_PAT", None)
    if not user_token:
        raise ValueError("Env variable 'GITHUB_PAT' required, but unset. ")

    smee_proxy_url = sys.argv[1]
    authorize_url = main(smee_proxy_url)

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
                    "GitHubApp": {
                        "id": response_json["id"],
                        "webhook_url": smee_proxy_url,
                        "webhook_secret": response_json["webhook_secret"],
                        "private_key": response_json["pem"],
                    }
                }
                with open(f"{CACHEDIR}/github_app_config.dev.yaml", "w") as f:
                    yaml.dump(app_config, f)

            return http.server.SimpleHTTPRequestHandler.do_GET(self)

    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print("To authorize a new dev app, navigate to", authorize_url)
        httpd.serve_forever()
