from datetime import datetime


def add_z(input_string: str) -> str:
    """Add a ``Z`` character the end of a timestamp string if needed, to bring it into
    compliance with ISO8601 formatting.
    """

    if not input_string.endswith("Z"):
        input_string += "Z"
    return input_string


def parse_to_datetime(input_string: str) -> datetime:
    input_string = add_z(input_string)
    return datetime.strptime(input_string, "%Y-%m-%dT%H:%M:%SZ")


def compare_response(response_fixture, reponse_data):
    for k, expected in response_fixture.items():
        actual = reponse_data[k]
        if isinstance(actual, datetime):
            assert actual == parse_to_datetime(expected)
        # Pydantic requires a "Z"-terminated timestamp, but FastAPI responds without the "Z"
        elif (
            isinstance(actual, str)
            and isinstance(expected, str)
            and any(s.endswith("Z") for s in (actual, expected))
            and not all(s.endswith("Z") for s in (actual, expected))
        ):
            assert add_z(actual) == add_z(expected)
        else:
            assert actual == expected


def create_with_dependencies(create_opts, mf, client):

    for dep in mf.dependencies:
        dep_create_opts = dep.model_fixture.create_opts[0]  # just use first create_opts
        dep_create_response = client.create(dep.model_fixture.path, dep_create_opts)
        compare_response(dep_create_opts, dep_create_response)

    data = client.create(mf.path, create_opts)

    return data
