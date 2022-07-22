# Pangeo Forge API

| Check           | Status                                                                                                                                                                                                              |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Linting         | [![pre-commit](https://github.com/pangeo-forge/pangeo-forge-orchestrator/actions/workflows/pre-commit.yaml/badge.svg)](https://github.com/pangeo-forge/pangeo-forge-orchestrator/actions/workflows/pre-commit.yaml) |
| Testing         | [![Tests](https://github.com/pangeo-forge/pangeo-forge-orchestrator/actions/workflows/main.yaml/badge.svg)](https://github.com/pangeo-forge/pangeo-forge-orchestrator/actions/workflows/main.yaml)                  |
| Coverage        | [![codecov](https://codecov.io/gh/pangeo-forge/pangeo-forge-orchestrator/branch/main/graph/badge.svg?token=ay8eJ6JUiX)](https://codecov.io/gh/pangeo-forge/pangeo-forge-orchestrator)                               |
| Heroku Pipeline | https://dashboard.heroku.com/pipelines/17cc0239-494f-4a68-aa75-3da7c466709c                                                                                                                                         |
| Staging API     | https://api-staging.pangeo-forge.org/docs                                                                                                                                                                           |
| Prod API        | https://api.pangeo-forge.org/docs                                                                                                                                                                                   |

## Overview

This is the FastAPI application for the Pangeo Forge main backend service.

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

### Review App

After the CI passes on a PR, Heroku creates a Review App which will hang around for two days.
This is a live version of the app running against an ephemeral database.
We could use this for manual checks or further integration testing.

### Staging Deployment

Changes merged to `main` will deploy the [pangeo-forge-api-staging](https://dashboard.heroku.com/apps/pangeo-forge-api-staging) app to the "staging" environment.
This is currently the only deployment configured in Heroku.
It app is configured with a `heroku-postgresql:hobby-0` add-on.
([Database control panel](https://data.heroku.com/datastores/1eae941d-caa0-405b-8e41-08f8959f7db2))

### Production Deployment

Changes merged to `prod` will deploy the [pangeo-forge-api-prod](https://dashboard.heroku.com/apps/pangeo-forge-api-prod) app to the "staging" environment.
This is currently the only deployment configured in Heroku.
It app is configured with a `heroku-postgresql:standard-0` add-on.
([Database control panel](https://data.heroku.com/datastores/bcd81fa2-0601-4882-b439-d5cefc63dfe3))

### DNS

DNS is managed at https://dns.he.net/ under Ryan's account.
It was configured following the [Heroku custom domains docs](https://devcenter.heroku.com/articles/custom-domains).
The two relevant records are:

| name                         | type  | TTL  | data                                                    |
| ---------------------------- | ----- | ---- | ------------------------------------------------------- |
| api-staging.pangeo-forge.org | CNAME | 1800 | ancient-woodland-ma1jj1m5y8687aopzbpq523p.herokudns.com |
| api.pangeo-forge.org         | CNAME | 1800 | powerful-harbor-5b6ajvki0ysxoh3gk56ksmi0.herokudns.com  |

Both staging and prod are set up with [automatic certificate management](https://devcenter.heroku.com/articles/automated-certificate-management).

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
> with tables based on `pangeo_forge_orchestrator.models`. If a file already exists at the at the `DATABASE_URL`, it will be updated
> to refect the tables defined by `pangeo_forge_orchestrator.models`. Note that `.sqlite` files are excluded by `.gitignore`, so you don't
> need to worry about the database file appearing in your commit. **You may, however, need to manually `rm database.sqlite` in between test
> sessions.**

Our Heroku CI tests (along with the production API) run with a Postgres server. Postgres implements certain features not present in SQLite.
As such, after your local tests passes against the SQLite database, you may want to test against a local Postgres server as a final check.
To do so:

1.  Install https://postgresapp.com
2.  Start the database using the app
3.  Run `echo "CREATE DATABASE test_db;" | psql` to create a database
4.  Set `export DATABASE_URL=postgresql://localhost/test_db`

        > If you are working on a PR that includes changes to `pangeo_forge_orchestrator.models`, you may need to generate a new alembic

    migration version before proceeding to Step 4. Refer to **Running Migrations** above for details.

5.  Run `python -m alembic upgrade head` to execute alembic migration against the new Postgres `DATABASE_URL`
6.  `pytest -vx`
