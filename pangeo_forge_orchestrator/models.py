from datetime import datetime
from enum import Enum
from typing import Optional

# from pydantic import validator
from sqlmodel import SQLModel

from .model_builders import MultipleModels


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
    :param path: The absolute path to the dataset built by this recipe run. This path will be
      deterministically defined by the Pangeo Forge dataset path specification at the time of
      execution. It is included here for convenience and backwards compatability.
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
    version: str
    path: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    conclusion: Optional[RecipeRunConclusion] = None
    status: RecipeRunStatus = RecipeRunStatus.queued
    message: Optional[str] = None

    # TODO: Replace `message` field with GitHub check runs `object`.
    # TODO: Validate `completed_at` field if provided.

    # @validator("conclusion")
    # def validate_conclusion_if_provided(cls, v):
    #    """Pydantic does not validate fields typed as `Optional` by default. To validate optional
    #    fields when they are provided, a custom `@validator` method is required. This method
    #    ensures that conclusion values outside those enumerated in `RecipeRunConclusion` will raise
    #    validation errors. (For more, see: https://github.com/samuelcolvin/pydantic/issues/1223.)
    #    """
    #     valid_opts = [opt.value for opt in RecipeRunConclusion]
    #    if v is not None:
    #        assert v in valid_opts
    #    return v


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
    "recipe_run": MultipleModels(path="/recipe_runs/", base=RecipeRunBase, response=RecipeRunRead)
}
