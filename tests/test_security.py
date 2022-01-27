import pytest


@pytest.mark.parametrize("api_key_options", [{}, {"is_admin": True}, {"is_admin": False}])
def test_api_key_create(client, api_key_options):
    with client.auth_required():
        # create is the same as post
        result = client.create("/api-keys", api_key_options)
    assert "key" in result
    assert result["is_active"] is True
    assert result["is_admin"] is api_key_options.get("is_admin", False)

    # TODO check that the key actually works
