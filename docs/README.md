Welcome to the `pangeo-forge-orchestrator` developer docs.

For simplicity, these docs are a collection of `.md` files. The easiest way to navigate them is using the Table of Contents below.

# Table of Contents

- [What is Pangeo Forge Orchestrator?](#what-is-pangeo-forge-orchestrator)

- [Detailed sequence diagrams](#updating-the-feedstock-repository)
  - [From staged-recipes PR to first prod run](#from-staged-recipes-pr-to-first-production-run)
  - [Updating the feedstock repository](#updating-the-feedstock-repository)

# What is Pangeo Forge Orchestrator?

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

In the following diagram, participants denoted with stars are deployed from `pangeo-forge-orchestrator`:

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

# -------------

## Overview

- [roadmap](roadmap.md) - A look at what's to come.
- [security](security.md) - How secrets are handled here.

## Application

The FastAPI app deployed from this repo serves two primary functions: to interface with a postgres database, and to interface with GitHub. For details of each of these roles, see:

- [database-api](database-api.md) - Details on database configuration and interface.
- [github-app](github-app.md) - Details on the GitHub App integration.

## Deployment

Every PR to `pangeo-forge-orchestrator` travels though a series of (up to) four deployments:

```mermaid
flowchart LR
    local-->review-->staging-->prod
```

> **Note**: Depending on the level of complexity of the PR, the `local` and/or `review` deployments may be omitted.

Instructions

- [deploy-local](deploy-local.md) -
- [deploy-heroku](deploy-heroku.md) -

Each

- [dataflow-status-monitoring](dataflow-status-monitoring.md)

## Testing

- [testing](testing.md)
