Welcome to the `pangeo-forge-orchestrator` developer docs.

We welcome anyone to contribute by opening issues on this repo. To contribute
code to this repo, you will need membership in:

- AWS `pangeo-forge` team (with KMS permissions)
- Heroku `pangeo-forge` team
- GitHub `pangeo-forge` org
- GitHub `pforgetest` org
- GCP `pangeo-forge-4967` project

Over time, we aim to establish a pathway for contributors
external to the above-listed teams to contribute code to this repository.

# Table of Contents

- [What is Pangeo Forge Orchestrator?](#what-is-pangeo-forge-orchestrator) - Introduces the four
  components deployed and/or configured by this repo, and their relationship to other components of
  Pangeo Forge Cloud.
- [Deployments: overview](#deployments-overview) - General presentation of the four deployment types,
  including naming format, resource locations for each deployment stage, and common requirements.
- [How to use SOPS](#how-to-use-sops) - Using SOPS to encrypt/decrypt repo secrets.
- [The local deployment](#the-local-deployment) - Setup a local deployment, with optional
  proxy server.
- [Heroku deployments](#heroku-deployments) - Overview of Heroku configuration and details
  on how to deploy each of the three Heroku deployments (review, staging, and prod).
- [Debugging Docker issues](#debugging-docker-issues) - Use docker-compose to debug Docker builds.
- [Database: migrations with Alembic](#database-migrations-with-alembic) - Generating new database
  versions automatically.
- [Database: manual edits](#database-manual-edits)
- [Bakeries: `pangeo-forge-runner` config](#bakeries-pangeo-forge-runner-config) - Configure named
  compute & storage backends.
- [Bakeries: job status monitoring](#bakeries-job-status-monitoring) - This is how the FastAPI app
  knows when compute jobs have concluded. Terraform for this infra is run on each Heroku deploy.
- [Security](#security) - Some notes on security.
- [Testing](#testing) - Automated testing in both local envs and production container contexts.
- [GitHub App: best practices](#github-app-best-practices) - Guidelines for developing the GitHub integration.
- [GitHub App: manual API calls](#github-app-manual-api-calls) - How to manually call the GitHub API _as a GitHub App_.
- [History & roadmap](#history--roadmap) - Where this platform started, where it's going.
- [Detailed sequence diagrams](#detailed-sequence-diagrams) - Fine-grained look at call stacks.

# What is Pangeo Forge Orchestrator?

This repo deploys and/or configures four difference components. These components, along with their deployment
locations, are represented in the following diagram:

```mermaid
flowchart

    GH_APP["GitHub App"]
    API["Pangeo Forge Cloud API (FastAPI)"]
    DB["Database (Postgres)"]
    DSM["Dataflow Status Monitoring"]

    subgraph Pangeo Forge Orchestrator
        direction TB

        subgraph GitHub
            GH_APP
        end

        GH_APP-->|sends webhooks| API
        API-->|authenticates as| GH_APP

        subgraph Heroku
            API-->|writes| DB
            DB-->|reads| API
        end

        subgraph Google Cloud
            DSM
        end

    API-->|deploys| DSM
    DSM-->|sends webhooks| API
    end

```

This next diagram demonstrates, in a general sense, how these four components interact with other components of
Pangeo Forge Cloud. Here, the four participants denoted with stars are those deployed/configured by `pangeo-forge-orchestrator`:

```mermaid
sequenceDiagram

    Feedstock Repo-->>GitHub App #9733;: event
    GitHub App #9733;-->>FastAPI #9733;: webhook
    FastAPI #9733;->>Database #9733;: records event
    FastAPI #9733;->>GitHub App #9733;: authenticates as
    GitHub App #9733;->>Feedstock Repo: to take action
    FastAPI #9733;->>Bakery: deploys jobs
    Bakery->>Status Monitoring #9733;: reports job status
    Status Monitoring #9733;-->>FastAPI #9733;: forwards job status
    FastAPI #9733;->>Database #9733;: records job status
    FastAPI #9733;->>GitHub App #9733;: authenticates as
    GitHub App #9733;->>Feedstock Repo: to report job status
    pangeo-forge.org-->>FastAPI #9733;: requests data
    FastAPI #9733;-->>Database #9733;: fetches data
    Database #9733;->>FastAPI #9733;: returns data
    FastAPI #9733;->>pangeo-forge.org: returns data
```

# Deployments: overview

Every PR to `pangeo-forge-orchestrator` travels though a series of (up to) four deployment types:

```mermaid
flowchart LR
    local-->review-->staging-->prod
```

Arbitrary numbers of `local` and `review` apps may exist simultaneously.
There is only ever one `staging` and one `prod` deployment.

## Naming

Deployment names are formatted as follows:

| type      | naming format                                      | example                    |
| --------- | -------------------------------------------------- | -------------------------- |
| `local`   | `pforge-local-${Developer's GitHub Username}`      | `pforge-local-cisaacstern` |
| `review`  | `pforge-pr-${pangeo-forge-orchestrator PR Number}` | `pforge-pr-136`            |
| `staging` | always named `pangeo-forge-staging`                | n/a                        |
| `prod`    | always named `pangeo-forge`                        | n/a                        |

## Resource locations

| type      | FastAPI | Database | GitHub App (Organizaton) | Status Monitoring (Terraform Env) |
| --------- | ------- | -------- | ------------------------ | --------------------------------- |
| `local`   | local   | local    | `pforgetest`             | `dev`                             |
| `review`  | Heroku  | Heroku   | `pforgetest`             | `dev`                             |
| `staging` | Heroku  | Heroku   | `pforgetest`             | `pangeo-forge-staging`            |
| `prod`    | Heroku  | Heroku   | `pangeo-forge`           | `pangeo-forge`                    |

## Common requirements

All deployments require:

1. A secrets config file named `secrets/config.${deployment-name}.yaml`:

   ```yaml
   # secrets/config.${deployment-name}.yaml

   fastapi:
     # this key is generated by `scripts.develop/generate_api_key.py`
     PANGEO_FORGE_API_KEY: ${api key for protected fastapi routes}
   github_app:
     app_name: ${the deployment name}
     # following fields are auto-generated by github on app creation
     # new apps are created with `scripts.develop/new_github_app.py`
     id: ${github app id}
     private_key: ${github app rsa private key}
     webhook_secret: ${github app hmac webhook secret}
   ```

2. `PANGEO_FORGE_DEPLOYMENT` env var. The deployment name, e.g. `pforge-pr-136`, or `pangeo-forge-staging`.
3. AWS CLI authentication. The AWS account must have read access to the `pangeo-forge` AWS project KMS.
4. `DATABASE_URL` env var. A valid SQLAlchemy URI pointing to a SQLite (for local deployments) or
   Postgres (for all other deployments) database.

# How to use SOPS

Credentials for each deployment are commited to the `pangeo-forge-orchestrator` repo as encrypted YAML.
Committing encrypted secrets directly to this repo allows for transparent and version-controlled
management of credentials. [SOPS](https://github.com/mozilla/sops) is used to encrypt and decrypt these
files. The [pre-commit-hook-ensure-sops](https://github.com/yuvipanda/pre-commit-hook-ensure-sops) and `gitleaks` hooks
installed in this repo's `.pre-commit-config.yaml` ensure that we don't accidentally commit unencrypted
secrets. For this reason, please always make sure that
[**pre-commit is installed**](https://pre-commit.com/#quick-start) in your local development environment.

The `sops.yaml` config in this repo instructs SOPS to use a particular pair of AWS KMS keys for
encryption and decryption of secrets. Members of the `pangeo-forge` AWS project with access to KMS
can use these keys for encrypt/decrypt operations.

## Setup

1. Make sure you are signed into the AWS CLI with `aws configure`.
2. Install SOPS. On MacOS, the easiest way is probably `brew install sops`.

## Encrypt

```console
$ sops -d -i secrets/${filename}
```

## Decrypt

```console
$ sops -e -i secrets/${filename}
```

# The `local` deployment

## Secret config

To generate these FastAPI credentials for the `local` deployment, from the repo root, run:

```console
$ python3 scripts.develop/generate_api_key.py local ${Your GitHub Username}
```

Now, `secrets/config.pforge-local-${Your GitHub Username}.yaml` should contain an api key.

Next, add GitHub App creds to

## Database

You will not be able to start your `local` dev server without first setting the `DATABASE_URL` env
variable, which tells the application where to connect to the database.

The easiest way to do this is by using a sqlite database, as follows:

```console
$ export DATABASE_URL=sqlite:///`pwd`/database.sqlite
```

The file `database.sqlite` does not need to exist before you start the application; the application will
create it for you on start-up. Note that of the four deployments described in the
[Deployment Lifecycle](#1-deployment-lifecycle) section above, the `local` deployment is the only once which
can use sqlite. All of the others use postgres:

|          | local | review | staging | prod |
| -------- | ----- | ------ | ------- | ---- |
| sqlite   | ✅    | ✖️     | ✖️      | ✖️   |
| postgres | ✅    | ✅     | ✅      | ✅   |

As noted by this table, the `local` deployment _can_ also run with postgres. This may be useful for
debugging issues related to postgres specifically. (The sqlite and postgres idioms, while similar, are
different enough that code developed _only_ against sqlite can sometimes fail against postgres.)

All Heroku deployments run with a Postgres server. Postgres implements certain features not present in
SQLite. As such, after your local tests passes against the SQLite database, you may want to test against
a local Postgres server as a final check. To do so:

1.  Install https://postgresapp.com
2.  Start the database using the app
3.  Run `echo "CREATE DATABASE test_db;" | psql` to create a database
4.  Set `export DATABASE_URL=postgresql://localhost/test_db`

    > If you are working on a PR that includes changes to `pangeo_forge_orchestrator.models`, you may
    > need to generate a new alembic migration version before proceeding to Step 4. Refer to **Running
    > Migrations** above for details.

5.  Run `python -m alembic upgrade head` to execute alembic migration against the new Postgres `DATABASE_URL`
6.  `pytest -vx`

#

# Heroku deployments

The application is configured to deploy on Heroku using Heroku pipelines.
Setting this up took some trial and error, but now it works great.
You need to read these documentation pages in order to fully understand the
Heroku configuation:

- [How Heroku Works](https://devcenter.heroku.com/articles/how-heroku-works)
- [Heroku Piplines](https://devcenter.heroku.com/articles/pipelines)
- [Heroku Review Apps](https://devcenter.heroku.com/articles/github-integration-review-apps)
- [Heroku Postgres](https://devcenter.heroku.com/articles/heroku-postgresql)

Pipeline main link: [pangeo-forge-api-flow](https://dashboard.heroku.com/pipelines/17cc0239-494f-4a68-aa75-3da7c466709c) (membership in Heroku `pangeo-forge` group required for access)

## Relevant files

- `Dockerfile` -
- `requirements.txt` - used to build the app's environment. Versions are pinned for stability.
  We will need to manually update these on a regular schedule.
- `heroku.yml` -
- `app.json` - more configuration, including
- `scripts.deploy/release.sh` -

## DNS

DNS is managed at https://dns.he.net/ under Ryan's account.
It was configured following the [Heroku custom domains docs](https://devcenter.heroku.com/articles/custom-domains).
The two relevant records are:

| name                         | type  | TTL  | data                                                    |
| ---------------------------- | ----- | ---- | ------------------------------------------------------- |
| api-staging.pangeo-forge.org | CNAME | 1800 | ancient-woodland-ma1jj1m5y8687aopzbpq523p.herokudns.com |
| api.pangeo-forge.org         | CNAME | 1800 | powerful-harbor-5b6ajvki0ysxoh3gk56ksmi0.herokudns.com  |

Both staging and prod are set up with [automatic certificate management](https://devcenter.heroku.com/articles/automated-certificate-management).

## `review`

After the CI passes on a PR, Heroku creates a Review App which will hang around for two days.
This is a live version of the app running against an ephemeral database.
We could use this for manual checks or further integration testing.

## `staging`

Changes merged to `main` will deploy the
[pangeo-forge-api-staging](https://dashboard.heroku.com/apps/pangeo-forge-api-staging)
app to the "staging" environment. This is currently the only deployment configured in Heroku.
It app is configured with a `heroku-postgresql:hobby-0` add-on.
([Database control panel](https://data.heroku.com/datastores/1eae941d-caa0-405b-8e41-08f8959f7db2))

## `prod`

Changes merged to `prod` will deploy the [pangeo-forge-api-prod](https://dashboard.heroku.com/apps/pangeo-forge-api-prod) app to the "staging" environment.
This is currently the only deployment configured in Heroku.
It app is configured with a `heroku-postgresql:standard-0` add-on.
([Database control panel](https://data.heroku.com/datastores/bcd81fa2-0601-4882-b439-d5cefc63dfe3))

# Debugging Docker issues

# Database: migrations with Alembic

This application is configured to use Alembic database migrations.
The configuration was pieced together from the following resources:

- Generic Alembic tutorial: https://alembic.sqlalchemy.org/en/latest/tutorial.html
- Using sqlmodel with Alembic: https://github.com/tiangolo/sqlmodel/issues/85#issuecomment-917228849

## Relevant Files

- `alembic.ini` - Alembic configuration file
- `migrations/env.py` - The migration environment; customized to work with
  sqlmodel our test / deployment environment
- `migrations/versions/*.py` - Auto-generated scripts which perform the migrations.

## `DATABASE_URL` Environment Variable

Both the migration environment and the FastAPI app itself are configured to use
the `DATABASE_URL` environment variable to determine which database to connect to.
**This environment variable must be set in order for the app to work.**
This string must be a valid sqlalchemy database URI.

The Heroku deployment environments automatically set this environment variable
to point to the appropriate postgres database.

## Running Migrations

The command

```bash
python -m alembic upgrade head
```

will initialize the database located at `DATABASE_URL` to the latest version of
the schema. If no tables are present, it will create them. If a different version
exists, it will migrate. For more details on how this works, see the Alembic docs.

**A migration must be run before the app is started on a fresh database!**
Otherwise the tables will not exist. (The app code itself no longer creates tables.)

## Creating a new Database Version

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

# Database: manual edits

# Bakeries: `pangeo-forge-runner` config

# Bakeries: job status monitoring

# Security

## Database API routes

Clients authenticate by providing their API key in the `X-API-Key` HTTP header.
The configuration is based loosely on https://github.com/mrtolkien/fastapi_simple_security.
Keys can be updated by decrypting credentials and re-running `scripts.develop/generate_api_key.py`.

There are currently two levels of authorization in the app

- _Unauthenticated Access_ - only GET operations
- _Authenticated Access_ - Anyone with a valid api key can POST, UPDATE, DELETE.

Moving forward, we will likely need to make this more fine-grained.
In particular, we may wish to associate API keys with bakeries and / or users,
and restrict permissions based on these properties. Todo:

- Implement key expiry policies
- Link keys to specific users and / or bakeries (i.e. service accounts

## GitHub App routes

Every webhook received from GitHub comes with a hash signature which certifies that it was actually sent
by GitHub (and not a hostile actor impersonating GitHub). The first thing that the `/github/hooks/` route
handler does after receiving a webhook is to verify this hash signature. Webhooks with a missing or
incorrect hash signature are rejected, and an error code is returned to the sender.

```mermaid
sequenceDiagram
    participant GitHub
    participant Orchestrator
    GitHub->>Orchestrator:delivers webhook request to "/github/hooks/"
    Orchestrator->>Orchestrator:verifies hash signature of webhook request
    Orchestrator->>GitHub:sends HTTP response
    Orchestrator->>Orchestrator:starts background task
    Orchestrator->>GitHub:background task registers its status via Checks API
```

For more on hash signature verification, see:

> https://docs.github.com/en/github-ae@latest/rest/guides/best-practices-for-integrators#secure-payloads-delivered-from-github

## Secrets

# Testing

# GitHub App: best practices

# GitHub App: manual API calls

# History & roadmap

subprocess.run vs. dockerized subprocess

# Detailed sequence diagrams

## From `staged-recipes` PR to first production run

```mermaid
sequenceDiagram
    autonumber
    actor Pangeo Forge Admin
    actor Contributor
    participant Staged Recipes Repo
    participant FastAPI
    participant Bakery
    participant Feedstock Repo


    %% ------------------------
    %% (1) Contributor opens PR
    %% ------------------------

    Contributor->>Staged Recipes Repo: opens PR
    Staged Recipes Repo-->>FastAPI: webhook: PR opened
    FastAPI->>FastAPI: creates `queued` recipe_run(s)
    FastAPI->>Staged Recipes Repo: updates check run status


    %% -----------------------------
    %% (2) Contributor commits to PR
    %% -----------------------------

    loop
    Contributor->>Staged Recipes Repo: commits to PR
    Staged Recipes Repo-->>FastAPI: webhook: new commits
    FastAPI->>FastAPI: creates `queued` recipe_run(s)
    FastAPI->>Staged Recipes Repo: updates check run status
    end


    %% ---------------------------
    %% (3) Admin deploys test /run
    %% ---------------------------

    loop
    Pangeo Forge Admin->>Staged Recipes Repo: deploys test /run
    Staged Recipes Repo-->>FastAPI: webhook: issue comment
    FastAPI->>FastAPI: updates recipe run to `in_progress`
    FastAPI->>Bakery: deploys test job


    %% ---------------------------
    %% (4) Job status notification
    %% ---------------------------

    Bakery-->>FastAPI: reports job status
    FastAPI->>FastAPI: updates recipe_run with job status
    FastAPI->>Staged Recipes Repo: reports job status
    end

    %% -------------------------
    %% (5) Create feedstock repo
    %% -------------------------

    Pangeo Forge Admin->>Staged Recipes Repo: merges PR
    Staged Recipes Repo-->>FastAPI: webhook: PR merged
    FastAPI->>Feedstock Repo: creates feedstock repo (empty)
    FastAPI->>FastAPI: records new feedstock
    FastAPI->>Feedstock Repo: opens PR w/ recipe.py + meta.yaml
    FastAPI->>Staged Recipes Repo: deletes PR files
    FastAPI->>Feedstock Repo: merges PR

    %% ----------------------------
    %% (6) Deploy production run(s)
    %% ----------------------------

    Feedstock Repo-->>FastAPI: webook: PR merged
    FastAPI->>FastAPI: creates recipe_run(s)
    FastAPI->>Feedstock Repo: creates deployment API env for each recipe run
    FastAPI->>Bakery: deploys prod run(s)


    %% ---------------------------
    %% (7) Job status notification
    %% ---------------------------

    Bakery-->>FastAPI: reports job status
    FastAPI->>FastAPI: updates recipe_run(s) w/ job status
    FastAPI->>Feedstock Repo: updates deployment API env(s) with job status

```

## Updating the feedstock repository

```mermaid

sequenceDiagram
    autonumber
    actor Maintainer
    participant Feedstock Repo
    participant FastAPI
    participant Bakery

    %% -------------------
    %% (1) PR to fix error
    %% -------------------

    Maintainer->>Feedstock Repo: opens PR
    Feedstock Repo-->>FastAPI: webhook: PR opened
    FastAPI->>FastAPI: creates `queued` recipe_run(s)
    FastAPI->>Feedstock Repo: updates check run status



    %% --------------------
    %% (2) Deploy test run
    %% --------------------
    loop
    Maintainer->>Feedstock Repo: deploys test /run
    Feedstock Repo-->>FastAPI: webhook: issue comment
    FastAPI->>FastAPI: updates recipe run to `in_progress`
    FastAPI->>Bakery: deploys test job

    Bakery-->>FastAPI: reports job status
    FastAPI->>FastAPI: updates recipe_run with job status
    FastAPI->>Feedstock Repo: reports job status
    end

    Maintainer->>Feedstock Repo: merges PR
    Feedstock Repo-->>FastAPI: webook: PR merged
    FastAPI->>FastAPI: repeats prod run -> Data User cycle described above

```
