import json
import os

from prefect.client.client import Client
from prefect.utilities.graphql import with_args

client = Client()


def new_automation(flow_group_id, pat_token):
    payload = {
        "event_type": "prefect_webhook",
        "client_payload": {
            "state": "{state}",
            "flow_run_id": "{flow_run_id}",
        },
    }
    headers = {"Authorization": f"token {pat_token}", "Accept": "application/vnd.github.v3+json"}

    payload_string = json.dumps(payload)
    headers_string = json.dumps(headers)

    repository = os.environ["GITHUB_REPOSITORY"]
    create_action = {
        "mutation": {
            with_args(
                "create_action",
                {
                    "input": {
                        "config": {
                            "webhook": {
                                "url": f"https://api.github.com/repos/{repository}/dispatches",
                                "payload": payload_string,
                                "headers": headers_string,
                            }
                        }
                    }
                },
            ): {"id"}
        }
    }
    action_response = client.graphql(create_action)
    action_id = action_response["data"]["create_action"]["id"]

    create_flow_run_state_changed_hook = {
        "mutation": {
            with_args(
                "create_flow_run_state_changed_hook",
                {
                    "input": {
                        "action_id": action_id,
                        "flow_group_ids": [flow_group_id],
                        "states": ["Success", "Failed"],
                    }
                },
            ): {"id"}
        }
    }
    hook_id = client.graphql(create_flow_run_state_changed_hook)
    print(hook_id)


def create_automation(flow_id, pat_token):
    flow_group_id_query = {
        "query": {
            with_args("flow", {"where": {"id": {"_eq": flow_id}}}): {
                "flow_group_id",
                "version_group_id",
            }
        }
    }
    flow_group_id_response = client.graphql(flow_group_id_query)
    flow_group_id = flow_group_id_response["data"]["flow"][0]["flow_group_id"]
    new_automation(flow_group_id, pat_token)
