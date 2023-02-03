import os

import pytest


@pytest.fixture
def app_url():
    """Url on the public internet at which the app to test against is currently running."""
    return os.environ["REVIEW_APP_URL"]


@pytest.fixture(params=[])
def content_files(request):
    """The content files to add. Parametrization of the ``test_dataflow`` test happens here."""
    ...
    yield ...


@pytest.fixture
def staged_recipes_pr(app_url, content_files):
    """Makes a PR to ``pforgetest/test-staged-recipes`` and labels it ``f"fwd:{app_url}{route}"``,
    where ``{route}`` is optionally the path at which the app running at ``app_url`` receives
    GitHub Webhooks. The label ``f"fwd:{app_url}{route}"`` informs the ``dev-app-proxy`` GitHub App
    where to forward webhooks originating from the PR. After the PR is created, its identifying
    information is yielded to the test function using this fixture. When control is returned to this
    fixture, the PR and its associated branch are closed & cleaned-up.
    """
    # create a new branch on pforgetest/test-staged-recipes with a descriptive name.
    # (in the typical contribution process, recipes are contributed from forks. the deviation from
    # that process here may introduce some sublte differences with production. for now, we are
    # accepting that as the cost for doing this more simply; i.e., all within a single repo.)
    ...

    # populate that branch
    ...

    # open a pr against pforgetest/test-staged-recipes:main
    pr = ...

    yield pr

    # close pr and cleanup branch
    ...


def test_dataflow(staged_recipes_pr):

    ...
    #
