from unittest.mock import patch

from pangeo_forge_prefect.automation_hook_manager import create_automation


@patch("pangeo_forge_prefect.automation_hook_manager.new_automation")
@patch("pangeo_forge_prefect.automation_hook_manager.client")
def test_create_automation(client, new_automation):
    flow_group_id = "flow_group_id"
    flow_qroup_query_response = {"data": {"flow": [{"flow_group_id": flow_group_id}]}}
    hook_query_response = {"data": {"hook": []}}
    client.graphql.side_effect = [flow_qroup_query_response, hook_query_response]
    create_automation("", "")
    new_automation.assert_called_once_with(flow_group_id, "")
