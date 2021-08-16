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
            "flow_run_id": "{flow_run_name}",
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
    """
    Create a Prefect Automation to call a Github repository webhook.

    Create a Prefect Automation that POSTs to a Github repository webhook
    when a test flow is registered.  The Github Action usess the flow_run_id
    (which is set to the trigger comment's id) to update the comment when the
    test flow run succeeds or fails.

    Parameters
    ----------
    flow_id : str
        The id of the registered flow
    pat_token : str
        A Github PAT token with at a minimum the repo scope.
    """
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

    hook_query = {
        "query": {
            with_args(
                "hook", {"where": {"event_tags": {"_contains": {"flow_group_id": [flow_group_id]}}}}
            ): {"id"}
        }
    }
    hook_query_response = client.graphql(hook_query)
    print(hook_query_response)
    hook_exists = len(hook_query_response["data"]["hook"]) > 0
    if hook_exists:
        delete_hook = {
            "mutation": {
                with_args(
                    "delete_hook",
                    {"input": {"hook_id": hook_query_response["data"]["hook"][0]["id"]}},
                ): {"success"}
            }
        }
        delete_hook_response = client.graphql(delete_hook)
        print(delete_hook_response)

    new_automation(flow_group_id, pat_token)
