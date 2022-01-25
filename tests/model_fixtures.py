"""
This is where we put all the data about creating / updating models
"""
from dataclasses import dataclass, field
from typing import Dict, List, Sequence, Union

APIOpts = Dict[str, Union[int, str]]


@dataclass
class ModelFixture:
    path: str
    required_fields: Sequence[str]
    create_opts: Sequence[APIOpts]  # valid ways to create the model
    invalid_opts: Sequence[APIOpts]  # setting these on creation or update should error
    update_opts: Sequence[APIOpts]  # setting these on update should be valid


@dataclass
class ModelRelationFixture:
    field_name: str  # Name of the field cooresponding to the related table
    model_fixture: ModelFixture


@dataclass
class ModelFixtureWithDependencies(ModelFixture):
    dependencies: List[ModelRelationFixture] = field(default_factory=list)  # req'd to create model


@dataclass
class ModelFixtureWithOptionalRelations(ModelFixture):
    optional_relations: List[ModelRelationFixture] = field(default_factory=list)  # not req'd


NOT_STR = {"not parsable": "to str"}
NOT_INT = "not parsable to int"
NOT_ISO8601 = "Jan 01 2021 00:00:00"


recipe_run_fixture = ModelFixtureWithDependencies(
    path="/recipe_runs/",
    required_fields=[
        "recipe_id",
        "bakery_id",
        "feedstock_id",
        "head_sha",
        "version",
        "started_at",
    ],
    create_opts=[
        dict(
            recipe_id="test-recipe-0",
            bakery_id=1,  # has to be `1`
            feedstock_id=1,  # has to be `1`
            head_sha="abcdefg12345",
            version="1.0",
            started_at="2021-01-01T00:00:00Z",
            completed_at="2021-01-01T01:01:01Z",
            conclusion="success",
            status="completed",
            message="hello",
        ),
        dict(
            recipe_id="test-recipe-1",
            bakery_id=1,  # has to be `1`
            feedstock_id=1,  # has to be `1`
            head_sha="012345abcdefg",
            version="2.0",
            started_at="2021-02-02T00:00:00Z",
            status="queued",
        ),
    ],
    invalid_opts=[
        dict(recipe_id=NOT_STR),  # type: ignore
        dict(bakery_id=NOT_INT),
        dict(feedstock_id=NOT_INT),
        dict(head_sha=NOT_STR),  # type: ignore
        dict(version=NOT_STR),  # type: ignore
        dict(started_at=NOT_ISO8601),
        dict(completed_at=NOT_ISO8601),
        dict(conclusion="not a valid conclusion"),
        dict(status="not a valid status"),
        dict(message=NOT_STR),  # type: ignore
        # the following two options should fail but don't
        # dict(id=100),  # shouldn't be able to pass id at all; instead silently ignored
        # dict(random_field_that_doesnt_exist_and_shouldnt_be_allow="foobar"),
    ],
    update_opts=[
        {"completed_at": "2021-01-02T01:01:01Z", "status": "completed", "conclusion": "failure"},
        {"completed_at": "2021-01-02T01:01:01Z", "status": "completed", "conclusion": "success"},
    ],
)

bakery_fixture = ModelFixtureWithOptionalRelations(
    path="/bakeries/",
    required_fields=["region", "name", "description"],
    create_opts=[
        dict(region="a", name="b", description="c"),
        dict(region="d", name="e", description="f"),
    ],
    invalid_opts=[
        dict(region=NOT_STR),  # type: ignore
        dict(name=NOT_STR),  # type: ignore
        dict(description=NOT_STR),  # type: ignore
    ],
    update_opts=[
        {"region": "x", "name": "y", "description": "z"},
        {"region": "q", "name": "r", "description": "s"},
    ],
)

feedstock_fixture = ModelFixtureWithOptionalRelations(
    path="/feedstocks/",
    required_fields=["github_repo"],
    create_opts=[dict(github_repo="a"), dict(github_repo="b")],
    invalid_opts=[
        dict(github_repo=NOT_STR),  # type: ignore
        dict(github_org="not a valid GitHubOrg"),
    ],
    update_opts=[{"github_repo": "c"}, {"github_repo": "d"}],
)

recipe_run_fixture.dependencies += [
    ModelRelationFixture("bakery", bakery_fixture),
    ModelRelationFixture("feedstock", feedstock_fixture),
]

bakery_fixture.optional_relations += [ModelRelationFixture("recipe_runs", recipe_run_fixture)]

feedstock_fixture.optional_relations += [ModelRelationFixture("recipe_runs", recipe_run_fixture)]

ALL_MODEL_FIXTURES = [recipe_run_fixture, bakery_fixture, feedstock_fixture]
