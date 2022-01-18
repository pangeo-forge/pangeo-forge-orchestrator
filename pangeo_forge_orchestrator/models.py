from datetime import datetime
from enum import Enum
from typing import Optional

from sqlmodel import SQLModel

from .model_builders import MultipleModels


class BakeryBase(SQLModel):
    """
    """

    region: str
    name: str
    description: str


class BakeryRead(BakeryBase):
    """
    """

    id: int


class RecipeRunStatus(str, Enum):
    """Categorical choices for ``RecipeRunBase.status``. Copied from the GitHub check runs API.
    """

    queued = "queued"
    in_progress = "in_progress"
    completed = "completed"


class RecipeRunConclusion(str, Enum):
    """Categorical choices for ``RecipeRunBase.conclusion``. Copied from the GitHub check runs API.
    """

    action_required = "action_required"
    cancelled = "cancelled"
    failure = "failure"
    neutral = "neutral"
    success = "success"
    skipped = "skipped"
    stale = "stale"
    timed_out = "timed_out"


class RecipeRunBase(SQLModel):
    """Information about a specific Pangeo Forge recipe run. Fields which are not specific to
    Pangeo Forge are explicitly copied from the GitHub check runs API.

    :param recipe_id: The recipe identifier as provided in its associated ``meta.yaml``.
    :param bakery_id: The id of the bakery on which the recipe is executed. Must be one of the ids
      defined in the official Pangeo Forge bakery database.
    :param feedstock_id: The name of the Pangeo Forge feedstock repository containing this recipe.
    :param head_sha: The feedstock repository commit from which this recipe run was executed.
    :param version: The two-element, dot-delimited semantic version of the feedstock in which the
      executed recipe resides. Versions begin at 1.0 and are of format {MAJ_VERSION}.{MIN_VERSION}.
    :param started_at: Time the run began, as an ISO 8601 timestamp: YYYY-MM-DDTHH:MM:SSZ.
    :param completed_at: Time the run ended, as an ISO 8601 timestamp: YYYY-MM-DDTHH:MM:SSZ.
    :param conclusion: Required if you provide completed_at or a status of completed. The final
      conclusion of the check. Can be one of action_required, cancelled, failure, neutral, success,
      skipped, stale, or timed_out.
    :param status: The current status. Can be one of queued, in_progress, or completed.
      Default: queued.
    :param message: Additional information about this recipe run.
    """

    # TODO: Aspects of GitHub check runs `conclusion` which we have yet to implement:
    #  1. When the conclusion is action_required, additional details should be provided on the site
    #     specified by details_url.
    #  2. Note: Providing conclusion will automatically set the status parameter to completed.
    #  3. You cannot change a check run conclusion to stale, only GitHub can set this.

    recipe_id: str
    bakery_id: int  # TODO: Foreign key
    feedstock_id: int  # TODO: Foreign key
    head_sha: str
    version: str  # TODO: use `ConstrainedStr`
    started_at: datetime
    completed_at: Optional[datetime] = None
    conclusion: Optional[RecipeRunConclusion] = None
    status: RecipeRunStatus = RecipeRunStatus.queued
    message: Optional[str] = None  # TODO: Replace with GitHub check runs `output`.


class RecipeRunRead(RecipeRunBase):
    """A container used to hold the responses to GET requests to the API; a.k.a. a "response
    model". As defined in the SQLModel docs linked below, "This ... declares that the id field is
    required when reading a [table] from the API, because a [table] read from the API will come
    from the database, and in the database it will always have an ID." For more, see:
    https://sqlmodel.tiangolo.com/tutorial/fastapi/multiple-models/#the-heroread-data-model. (Note
    that "id" is just another way of saying "primary key".)
    """

    id: int


MODELS = {
    "recipe_run": MultipleModels(path="/recipe_runs/", base=RecipeRunBase, response=RecipeRunRead),
    "bakery": MultipleModels(path="/bakeries/", base=BakeryBase, response=BakeryRead),
}
