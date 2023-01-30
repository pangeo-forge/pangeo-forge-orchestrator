"""
This is where we put all the data about creating / updating models
"""
from dataclasses import dataclass, field
from typing import Sequence, Union

APIOpts = dict[str, Union[int, str]]


@dataclass
class ModelFixture:
    path: str
    required_fields: Sequence[str]
    create_opts: Sequence[APIOpts]  # valid ways to create the model
    invalid_opts: Sequence[APIOpts]  # setting these on creation or update should error
    update_opts: Sequence[APIOpts]  # setting these on update should be valid
    dependencies: list["ModelRelationFixture"] = field(default_factory=list)  # req to create model
    optional_relations: list["ModelRelationFixture"] = field(default_factory=list)  # not required

    @property
    def all_relations(self):
        return self.dependencies + self.optional_relations


@dataclass
class ModelRelationFixture:
    # For models with `sqlmodel.Relationship` attributes, holds data for creating the related table
    # in test database. Related tables may be either be required (i.e. a dependency) or optional.
    field_name: str  # Name of the field corresponding to the related table
    model_fixture: ModelFixture  # Data for populating the related table


NOT_BOOL = "not parsable to boolean"
NOT_STR = {"not parsable": "to str"}
NOT_INT = "not parsable to int"
NOT_ISO8601 = "Jan 01 2021 00:00:00"


recipe_run_fixture = ModelFixture(
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
        dict(is_test=NOT_BOOL),
        dict(dataset_type="not a valid dataset type"),
        dict(dataset_public_url=NOT_STR),  # type: ignore
        # the following two options should fail but don't
        # dict(id=100),  # shouldn't be able to pass id at all; instead silently ignored
        # dict(random_field_that_doesnt_exist_and_shouldnt_be_allow="foobar"),
    ],
    update_opts=[
        dict(completed_at="2021-01-02T01:01:01Z", status="completed", conclusion="failure"),
        dict(
            completed_at="2021-01-02T01:01:01Z",
            status="completed",
            conclusion="success",
            dataset_type="zarr",
            dataset_public_url="http://datahost.org/path-to-dataset",
        ),
    ],
)

bakery_fixture = ModelFixture(
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

feedstock_fixture = ModelFixture(
    path="/feedstocks/",
    required_fields=["spec"],
    create_opts=[dict(spec="a"), dict(spec="b")],
    invalid_opts=[
        dict(spec=NOT_STR),  # type: ignore
        dict(provider="not a valid RepoProvider"),
    ],
    update_opts=[{"spec": "c"}, {"spec": "d"}],
)

recipe_run_fixture.dependencies += [
    ModelRelationFixture("bakery", bakery_fixture),
    ModelRelationFixture("feedstock", feedstock_fixture),
]

bakery_fixture.optional_relations += [ModelRelationFixture("recipe_runs", recipe_run_fixture)]

feedstock_fixture.optional_relations += [ModelRelationFixture("recipe_runs", recipe_run_fixture)]

# TODO: Use actual `pytest.fixture`s. In particular, this will allow us to eliminate workarounds in
# the test suite such as `clear_table` and `create_with_dependencies` helper functions (each of
# which can be handled with fixture features such as requesting other fixtures, and teardowns). Note
# also that foreign keys can be assigned at runtime (rather than passed explicitly in `create_opts`)
# and that teardowns can manage deletion order so as not to raise Postgres `ForeignKeyViolation`s,
# which occur if rows references by other tables are deleted before the referencing rows. Further
# details in the following prior discussion:
# https://github.com/pangeo-forge/pangeo-forge-orchestrator/pull/40#issuecomment-1022804987
# https://github.com/pangeo-forge/pangeo-forge-orchestrator/pull/40#issuecomment-1022808293

ALL_MODEL_FIXTURES = [recipe_run_fixture, bakery_fixture, feedstock_fixture]
