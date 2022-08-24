# Development Guide

This combination guide and step-by-step tutorial walks through the development process
from setup of a local dev environment, through making your first PR to `pangeo-forge-orchestrator`.

- [1 Deployment Lifecycle](#1-deployment-lifecycle)
- [2 Getting started: the local deployment](#2-getting-started-the-local-deployment)
  - [2.1 Generating credentials](#21-generating-credentials)
    - [2.1.1 GitHub App](#211-github-app)
    - [2.1.2 FastAPI](#212-fastapi)
  - [2.2 Encrypting & committing creds](#22-encrypting--committing-creds)
  - [2.3 Database](#23-database)
  - [2.4 The proxy: selection & setup](#24-the-proxy-selection--setup)
  - [2.5 Start the server](#25-start-the-server)
- [3 Sending payloads to `local` deployment]()
  - [3.1 Creating a mock feedstock repo on GitHub]()
    - [3.1.1 Mocking pangeo-forge/staged-recipes]()
    - [3.1.2 Mocking pangeo-forge/dataset-feedstock]()
  - [3.2 Installing the `local` app in a mock feedstock]()
  - [3.3 Triggering events from the mock feedstock]()
  - [3.4 Debugging event webhooks]()
- [4 Adding features: design principles]()
  - [4.1]()
  - [4.2]()
  - [4.3]()
- [5 Next steps: the `review` deployment]()
  - [5.1 Open a PR]()
  - [5.2 Create, encrypt, and commit `review` credentials]()
- [6 Before merge: automated testing]()
  - [6.1 Mocking payloads]()
  - [6.2 Local run]()
    - [6.2.1 sqlite]()
    - [6.3.2 postgres]()
  - [6.3 Containerized run]()
    - [6.3.1 Starting the containerized services]()
    - [6.3.2 Testing on the containerized services]()
- [7 Finally: from `staging` to `prod`]()

# 1 Deployment Lifecycle

Every PR to `pangeo-forge-orchestrator` travels though a series of four deployments.

```mermaid
flowchart LR
    local-->review-->staging-->prod
```

Each of these deployments requires a set of credentials to run. These are kept in the
`secrets` directory of this repo.

```
...
├── secrets
│   ├── config.local.yaml
│   ├── config.review.yaml
│   ├── config.staging.yaml
│   └── config.prod.yaml
...
```

The user creates and provides `local` and `review` credentials for their PRs, whereas the organization
(i.e., `pangeo-forge`) manages credentials for the `staging` and `prod` deployments.

```mermaid
flowchart LR
    subgraph organization
    staging-->prod
    end
    subgraph user
    local-->review
    end
    review-->staging
```

Credentials for each deployment are commited to the `pangeo-forge-orchestrator` repo as encrypted YAML.
Committing encrypted secrets directly to this repo allows for transparent and version-controlled management
of credentials. [SOPS](https://github.com/mozilla/sops) is used to encrypt and decrypt these files. The
[pre-commit-hook-ensure-sops](https://github.com/yuvipanda/pre-commit-hook-ensure-sops) hook installed in
this repo's `.pre-commit-config.yaml` ensures that we don't accidentally commit unencrypted secrets. For this
reason, please always make sure that [**pre-commit is installed**](https://pre-commit.com/#quick-start)
in your local development environment.

# 2 Getting started: the local deployment

## 2.1 Generating credentials

Before starting work on your PR, you will need a local deployment of the application to work with. In order to
run this deployment, you will need to generate credentials for a new GitHub App instance, as well as for FastAPI.

### 2.1.1 GitHub App

[GitHub Apps](https://docs.github.com/en/developers/apps/getting-started-with-apps/about-apps#about-github-apps)
are a mechanism by which third party integrations can receive webhooks and take authenticated
actions on GitHub. Users and organizations can both create GitHub Apps within their accounts. As indicated by
the diagram in [Deployment Lifecycle](#1-deployment-lifecycle), users create and manage credentials for
GitHub Apps associated with their `local` and `review` deployments.

> **Note**: You may be wondering, if this is a `local` deployment, why do I need a _real_ GitHub App at all?
> Shouldn't the `local` deployment run entirely _locally_ on my own machine? This a good question. The answer is
> that while the `pangeo-forge-orchestrator` instance will run locally, the easiest and most reliable way to
> generate webhook inputs for your local instance is to connect it (via a "tunnel" or proxy) to a
> corresponding _real_ GitHub App. Without doing this, we must generate mock payloads ourselves, which is a
> time-consuming and potentially error-prone process (insofar as our mock payloads may not perfectly match
> those delivered by a real GitHub event). Ultimately, all features of the `pangeo-forge-orchestrator` app
> should be tested in `pytest` using mock payloads, but during the development process, its easiest not to
> have to simulate these payloads ourselves, which is why we're creating a real GitHub App now.

To authorize creation of a GitHub App instance in your user account for your `local` deployment, first assign
the env var `GITHUB_PAT` to a GitHub [Personal Access Token](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token#creating-a-token)
(with `repo` scope) for your user account:

```console
$ export GITHUB_PAT=${your_personal_access_token}
```

To programmatically create GitHub Apps, GitHub requires authentication via an in-browser oauth flow. The script
we use to create the `local` app instance, therefore, starts a local webserver to walk you through this flow. From the repo root, run:

```console
$ python3 scripts/new_github_app.py $YOUR_GITHUB_USERNAME local
```

You should see the following in your terminal:

```
To authorize a new dev app, navigate to http://localhost:3000/authorize.html
```

Navigate to http://localhost:3000/authorize.html. You should see something like this:

![GitHub App Manifest submit manifest example](/docs/_static/submit-manifest-example.png)

> **Do not** manually edit any of the JSON parameters in the input field; they have been programmatically
> generated for you by `scripts/new_github_app.py`. **_Do_ be aware**, however, that from this point forward
> you will be authorizing creation of a new GitHub App in your _real_ user account. If you have any
> reservations about this, please review `scripts/new_github_app.py` closely and/or dicuss with a Pangeo Forge
> maintainer before proceeding.

If you are ready to create a new GitHub App in your user account, click **Submit**. This button will redirect
you to GitHub, where you may be asked to login (or not, if your browser session credentials are still valid),
and then to a GitHub page which will prompt you to create a new GitHub App in your user account:

![GitHub App creation page example](/docs/_static/create-app-example.png)

Clicking the green button will create the `local` development app, and redirect you to a page like this:

![GitHub App creds created example](/docs/_static/creds-created-example.png)

where `/workdir` where will be replaced with the path in which your clone of `pangeo-forge-orchestrator` is stored.

🎉 Congratulations, you've created the GitHub App instance for your `local` deployment.
Navigating to https://github.com/settings/apps should now show you something like this (except
with your username in the app's name):

![GitHub App settings example](/docs/_static/app-settings-example.png)

As indicated by the redirect page screenshotted above, the credentials for this GitHub App,
including a private key and a webhook secret, will now be stored in the
`secrets/config.local.yaml` path within this repo.

This GitHub App will need a little bit more configuration before we can use it, which we will
address in [section 2.4](#24-the-proxy-selection--setup) below. This remaining configuration is
not related to credentials, however, so we will pause on this subject momentarily, and move on
to generating FastAPI credentials.

### 2.1.2 FastAPI

In addition to GitHub App credentials, each deployment requires FastAPI credentials. These are the

### 2.2 Encrypting & committing creds

Currently, we use the
[`age` backend](https://github.com/mozilla/sops#encrypting-using-age) for SOPS.

## 2.3 Database

|          | local | review | staging | prod |
| -------- | ----- | ------ | ------- | ---- |
| sqlite   | ✅    | ✖️     | ✖️      | ✖️   |
| postgres | ✅    | ✅     | ✅      | ✅   |

# 2.4 The proxy: selection & setup

## 2.5 Start the server
