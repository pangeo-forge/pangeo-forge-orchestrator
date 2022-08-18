# GitHub App

Advantages of GitHub App:

- More robust auth story
- Single point of configuration for webhooks and taking authenticated actions

## Setup a development environment

A little bit involved. To preview we'll set up:

- A new GitHub App
- A local smee client
- A local FastAPI instance
- A sandbox repository on your personal GitHub account in which to install the GitHub App

With these four components set up, you have everything you need to run Pangeo Forge.

> Dataflow development requires additional credentials. Maybe if its a development app, we
> can add special args to use the `pangeo-forge-runner` direct runner, rather than Dataflow?

### Create a new dev app

1. Create a smee channel, and copy its full url

   ```console
   export SMEE_URL=https://smee.io/brlCfGukG7f5BXv
   ```

2. From repo root, run
   ```console
   python3 scripts/new_dev_app.py $SMEE_URL
   ```
3. Navigate to http://localhost:3000/authorize.html and click **Submit**
4. Follow the unscreen prompts to authorize a GitHub App to be created in your user account
5. You may now `Ctrl+C` out of the webserver process started by `scripts/new_dev_app.py`
6. Your `github_app_config.dev.yaml` will be saved into the `.github_app_manifest_flow/` directory
7. From the repo root, set
   ```console
   export GITHUB_APP_CONFIG_PATH=`pwd`/.github_app_manifest_flow/github_app_config.dev.yaml
   ```

> A note on `scripts/new_dev_app.py`... why is it so complicated? The only way to make a GitHub App
> instance _from a manifest_ is to use a web browser, for authentication.

### Start the smee client

```
smee
```

### Start the FastAPI dev server

From the repo root, run:

```
uvicorn pangeo_forge_orchestrator.api:app --reload --reload-dir=`pwd`/pangeo_forge_orchestrator
```

```mermaid
sequenceDiagram
    participant GitHub
    participant Orchestrator
    GitHub->>Orchestrator:delivers webhook request to "/github/hooks"
    Orchestrator->>Orchestrator:verifies hash signature of webhook request
    Orchestrator->>GitHub:sends HTTP response
    Orchestrator->>Orchestrator:starts background task
    Orchestrator->>GitHub:background task registers its status via Checks API

```
