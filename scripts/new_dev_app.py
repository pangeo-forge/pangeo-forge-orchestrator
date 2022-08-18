import json
import os
import subprocess
import sys
import webbrowser
from urllib.parse import urlparse

cachedir = f"{os.getcwd()}/.github_app_manifest_flow"


def create_redirect_page():
    outpath = f"{cachedir}/redirect.html"
    content = """
    <html>
        You've been redirected
        Your code is <input id="conversion_code">
        <script>
            input = document.getElementById("conversion_code")
            const urlParams = new URLSearchParams(window.location.search);
            const conversion_code = urlParams.get('code');
            input.value = conversion_code
        </script>
    </html>
    """

    with open(outpath, "w") as f:
        f.write(content)

    return "http://localhost:3000/redirect.html"


def main(smee_proxy_url):
    """ """
    os.mkdir(cachedir)
    redirect_url = create_redirect_page()
    p = urlparse(smee_proxy_url)
    abbreviated_smee_channel_id = p.path[1:8]
    proxy_url_without_scheme = p.netloc + p.path
    manifest = dict(
        name=f"pangeo-forge-dev-{abbreviated_smee_channel_id}",
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
    page = f"""
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

    outpath = "page.html"

    with open(f"{cachedir}/{outpath}", "w") as f:
        f.write(page)

    return outpath


if __name__ == "__main__":
    cmd = f"python3 -m http.server 3000 --bind 127.0.0.1 --directory {cachedir}".split()
    p = subprocess.Popen(cmd, cwd=os.getcwd())
    smee_proxy_url = sys.argv[1]
    outpath = main(smee_proxy_url)
    webbrowser.open(f"http://localhost:3000/{outpath}")
