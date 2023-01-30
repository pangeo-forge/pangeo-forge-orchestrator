import json
import os

import requests

if __name__ == "__main__":

    ORG_NAME = os.environ["ORG_NAME"]
    GH_API_TOKEN = os.environ["GH_API_TOKEN"]

    query = f"""
    query ($cursor: String) {{
    organization(login: "{ORG_NAME}") {{
        repositories(first: 100, after: $cursor) {{
        pageInfo {{
            endCursor
            hasNextPage
        }}
        edges {{
            node {{
            name
            description
            url
            isPrivate
            }}
        }}
        }}
    }}
    }}
    """

    headers = {"Authorization": f"Bearer {GH_API_TOKEN}", "Content-Type": "application/json"}

    all_repos = []

    has_next_page = True
    cursor = None

    while has_next_page:
        variables: dict[str, str | None] = {"cursor": cursor} if cursor else {}
        response = requests.post(
            "https://api.github.com/graphql",
            json={"query": query, "variables": variables},
            headers=headers,
        )
        data = response.json()
        repos = data["data"]["organization"]["repositories"]["edges"]

        urls = [repo["node"]["url"] for repo in repos]
        all_repos.extend(urls)

        page_info = data["data"]["organization"]["repositories"]["pageInfo"]
        has_next_page = page_info["hasNextPage"]
        cursor = page_info["endCursor"]

    # write all_repos to a JSON string
    repos_json = json.dumps(all_repos)
    # set the output for GitHub Actions: https://github.com/orgs/community/discussions/28146
    print(f"::set-output name=repos::{repos_json}")
