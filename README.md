# pangeo-forge-orchestrator
A central place for introspecting and executing the various modular components of Pangeo Forge.

[![Tests](https://github.com/pangeo-forge/pangeo-forge-orchestrator/actions/workflows/main.yaml/badge.svg)](https://github.com/pangeo-forge/pangeo-forge-orchestrator/actions/workflows/main.yaml)
[![pre-commit](https://github.com/pangeo-forge/pangeo-forge-orchestrator/actions/workflows/pre-commit.yaml/badge.svg)](https://github.com/pangeo-forge/pangeo-forge-orchestrator/actions/workflows/pre-commit.yaml)
[![Documentation Status](https://readthedocs.org/projects/pangeo-forge-orchestrator/badge/?version=latest)](https://pangeo-forge-orchestrator.readthedocs.io/en/latest/?badge=latest)
[![codecov](https://codecov.io/gh/pangeo-forge/pangeo-forge-orchestrator/branch/main/graph/badge.svg?token=ay8eJ6JUiX)](https://codecov.io/gh/pangeo-forge/pangeo-forge-orchestrator)


## Database Migrations with Alembic

This application is configured to use Alembic database migrations.
The configuration was pieced together from the following resources:

- Generic Alembic tutorial: https://alembic.sqlalchemy.org/en/latest/tutorial.html
- Using sqlmodel with Alembic: https://github.com/tiangolo/sqlmodel/issues/85#issuecomment-917228849

### Relevant Files

- `alembic.ini` - Alembic configuration file
- `migrations/env.py` - The migration environment; customized to work with
  sqlmodel our test / deployment environment
- `migrations/versions/*.py` - Auto-generated scripts which perform the migrations.

### `DATABASE_URL` Environment Variable

Both the migration environment and the FastAPI app itself are configured to use
the `DATABASE_URL` environment variable to determine which database to connect to.
**This environment variable must be set in order for the app to work.**
This string must be a valid sqlalchemy database URI.

The Heroku deployment environments automatically set this environment variable
to point to the appropriate postgres database.

### Running Migrations

The command

```bash
python -m alembic upgrade head
```

will initialize the database located at `DATABASE_URL` to the latest version of
the schema. If no tables are present, it will create them. If a different version
exists, it will migrate. For more details on how this works, see the Alembic docs.

**A migration must be run before the app is started on a fresh database!**
Otherwise the tables will not exist. (The app code itself no longer creates tables.)

### Creating a new Database Version

Any time the SQLModel table models are changed in any way, a new migration
script has to be generated. _This is done automatically by Alembic!_ It's magic.
To create a new migration script, simply edit the models and then run.

```python
python -m alembic revision --autogenerate -m "Description of migration"
```

(Syntax and concepts are very similar to Git.)
This will place a new script in `migrations/versions/` which Alembic will run
when we want to migrate.
If the migration is complex or ambiguous, the migration script might have to be
tweaked manually.


## Local Testing

Migrations are not used for local testing with SQLite. To setup local testing, simply define the `DATABASE_URL` environment variable

```bash
export DATABASE_URL=sqlite:///`pwd`/database.sqlite
```
and then invoke the tests

```bash
pytest -vx
```

> If no file exists at the `DATABASE_URL`, a new SQLite database file will be automatically created for the test session and populated
with tables based on `pangeo_forge_orchestrator.models`. If a file already exists at the at the `DATABASE_URL`, it will be updated
to refect the tables defined by `pangeo_forge_orchestrator.models`. Note that `.sqlite` files are excluded by `.gitignore`, so you don't
need to worry about the database file appearing in your commit.

## Heroku Deployment

The application is configured to test and deploy on Heroku using Heroku pipelines.
Setting this up took some trial and error, but now it works great.
You need to read these documentation pages in order to fully understand the
Heroku configuation:

- [How Heroku Works](https://devcenter.heroku.com/articles/how-heroku-works)
- [Heroku Piplines](https://devcenter.heroku.com/articles/pipelines)
- [Heroku CI](https://devcenter.heroku.com/articles/heroku-ci)
- [Heroku Review Apps](https://devcenter.heroku.com/articles/github-integration-review-apps)
- [Heroku Postgres](https://devcenter.heroku.com/articles/heroku-postgresql)

Pipeline main link: [pangeo-forge-api-flow](https://dashboard.heroku.com/pipelines/17cc0239-494f-4a68-aa75-3da7c466709c) (membership in Heroku `pangeo-forge` group required for access)

### Relevant files

- `runtime.txt` - tells Heroku which runtime to use to build the app.
- `requirements.txt` - used to build the app's environment. Versions are pinned for stability.
   We will need to manually update these on a regular schedule.
- `Procfile` - tells Heroku how to deploy the app.
- `app.json` - more configuration, including the test scripts run by Heroku CI

### Heroku CI

Heroku CI is like GitHub Workflows or Travis CI. It runs the test suite in the Heroku environment.
The test script is located in `app.json`. It uses an ephemeral `heroku-postgresql:in-dyno` database.
Heroku CI integrates with GitHub and registers a check-run on PRs to the GitHub repo.

**Issue: [Heroku CI doesn't run on forks to public repos](https://devcenter.heroku.com/changelog-items/1208)**

> When opening or pushing to Pull Requests originating from forked, public GitHub repositories, Heroku CI will no longer automatically create a test run. Pull requests from private forks and un-forked (public or private) repositories will continue to create test runs as before.

This is for security reasons; doing so would allow anyone to execute aribtrary code inside
Heroku at any time. For this reason and others, _we should consider making this repo private_.

### Review App

After the CI passes on a PR, Heroku creates a Review App which will hang around for two days.
This is a live version of the app running against an ephemeral database.
We could use this for manual checks or further integration testing.

### Staging Deployment

Changes merged to `main` will deploy the [pangeo-forge-api-staging](https://dashboard.heroku.com/apps/pangeo-forge-api-staging) app to the "staging" environment.
This is currently the only deployment configured in Heroku.
It app is configured with our `heroku-postgresql:standard-0` add-on.
The control panel for the database is at https://data.heroku.com/datastores/db22cc7c-e6fe-4a70-ab38-3b6195e59a1c

### Production Deployment

Production app is not yet configured.
