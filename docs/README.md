- [Development Guide](development_guide.md)
- [Heroku](heroku.md)
- [Migrations](migrations.md)
- []
- [Testing](testing.md)

# 1 Deployment Lifecycle

Every PR to `pangeo-forge-orchestrator` travels though a series of four deployments.

```mermaid
flowchart LR
    local-->review-->staging-->prod
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

Each of these deployments requires a set of credentials to run. These are kept in the
`secrets` directory of this repo.

```
...
├── secrets
│   ├── config.pforge-local-cisaacstern.yaml    <- local creds for developer `cisaacstern`
│   ├── config.pforge-pr-80.yaml                <- review creds for `orchestrator` PR 80
│   ├── config.pangeo-forge-staging.yaml        <- staging creds
│   └── config.pangeo-forge.yaml                <- prod creds
...
```

Credentials for each deployment are commited to the `pangeo-forge-orchestrator` repo as encrypted YAML.
Committing encrypted secrets directly to this repo allows for transparent and version-controlled management
of credentials. [SOPS](https://github.com/mozilla/sops) is used to encrypt and decrypt these files. The
[pre-commit-hook-ensure-sops](https://github.com/yuvipanda/pre-commit-hook-ensure-sops) hook installed in
this repo's `.pre-commit-config.yaml` ensures that we don't accidentally commit unencrypted secrets. For this
reason, please always make sure that [**pre-commit is installed**](https://pre-commit.com/#quick-start)
in your local development environment.

# 6 Next steps: the `review` deployment

## 6.1 Open a PR

https://pangeo-forge-api-pr-80.herokuapp.com will be broken

## 6.2 Create, encrypt, and commit `review` credentials

1. Run `scripts/new_github_app.py` with the arguments `GITHUB_USERNAME review PR_NUMBER`. For example,
   for GitHub username `cisaacstern`, with PR number `80`, the script would be called like this:
   `console $ python3 scripts/new_github_app.py cisaacstern review 80 `
2. Follow in-browser prompts to create a new GitHub App.
3. Add FastAPI creds for the `review` app:
   ```console
   $ python3 scripts/generate_api_key.py review
   ```
4. Encrypt the creds:

   ```
   sops -e -i secrets/config.review.yaml
   ```

5. Commit the encrypted `secrets/config.review.yaml` and push it to your PR branch.

   > Note: If your local creds are still decrypted, you might want to just:
   >
   > ```console
   > $ git add secrets/config.review.yaml
   > ```

## 6.3 Check the `review` deployment

On the PR discussion thread you should see a notification that the review app deployment is "pending".
When the review app deployment is complete, you will see something like this:

![view deployment example](/docs/_static/view-deployment-example.png)

Click **View deployment**, which will bring you to a url such as https://pangeo-forge-api-pr-80.herokuapp.com.

Confirm that the root path of the deployment displays:

```
{"status":"ok"}
```

If the deployment displays another message, such as "Application error", the deployment has failed.
Confirm that you have correctly created, encrypted, and committed your `secrets/config.review.yaml`
file, as described above. If you believe the issue is not with the review app credentials, or need

## 6.4 Complete GitHub App setup

### 6.4.1 Update webhook url

### 6.4.2 Install app in your mock feedstock(s)

> TODO: Add feature for filtering based on GitHub PR labels. Otherwise we either:
>
> - need separate feedstock repos for each app version we're testing.
> - or will get duplicate responses to each repo.
