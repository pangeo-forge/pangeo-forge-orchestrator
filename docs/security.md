# Application Security

Security is currently implemented as API-key based authorization / authentication.

## Authentication

Clients authenticate by providing their API key in the `X-API-Key` HTTP header.
The configuration is based loosely on https://github.com/mrtolkien/fastapi_simple_security.

### Key Storage

The API keys are UUID4 values encoded as hex strings.

### Updating Keys

Keys can be updated by decrypting credentials and re-running `scripts.develop/generate_api_key.py`.

## Authorization

There are currently two levels of authorization in the app

- _Unauthenticated Access_ - only GET operations
- _Authenticated Access_ - Anyone with a valid api key can POST, UPDATE, DELETE.

Moving forward, we will likely need to make this more fine-grained.
In particular, we may wish to associate API keys with bakeries and / or users,
and restrict permissions based on these properties.

## TODO

- Implement key expiry policies
- Link keys to specific users and / or bakeries (i.e. service account)
- Add a "comment" field to the api keys table to remember ourselves what a particular
  key was created for.

### 2.2 Encrypting & committing creds

🥇 Great work! You should now have a `secrets/config.local.yaml` with all the credentials required for your
`local` deployment. While it is not strictly necessary to commit these credentials to the repo (because they
are for your local dev environment), this is a good opportunity to practice encrypting credentials (which
_will_ be required for the `review` deployment later on). Moreover, managing all credentials (including for
`local` deployment) in a uniform manner simplifies the process.

#### 2.2.1 pre-commit-hook-ensure-sops

⚠️ If you have not yet made sure that [**pre-commit is installed**](https://pre-commit.com/#quick-start) in
your local development environment, now is the time to do so! If you do not install pre-commit,
[pre-commit-hook-ensure-sops](https://github.com/yuvipanda/pre-commit-hook-ensure-sops) cannot protect you
from accidentally committing unencrypted credentials.

Assuming you have pre-commit installed (really, ☝️ read the warning above if you haven't already 😄), you will
be protected from committing your (currently unencrypted) credentials:

```console
$ git commit -m "add local config"
Ensure secrets are encrypted with sops...................................Failed
- hook id: sops-encryption
- exit code: 1

secrets/config.local.yaml: sops metadata key not found in file, is not properly encrypted
```

#### 2.2.2 Encryption

> **Note**: From this point forward, you will need be a member of the `pangeo-forge` AWS project
> with KMS permissions, and be logged in via `aws configure`.

1. Install [SOPS](https://github.com/mozilla/sops). The easiest way to do this on Mac is probably
   [`brew install sops`](https://formulae.brew.sh/formula/sops).
2. From the repo root, run:
   ```console
   $ sops -e -i secrets/config.local.yaml
   ```
   The `-e` indicates `encrypt` and the `-i` is for "in place".

Your credentials are now encrypted! You can commit them to the repo now. We will revisit how to decrypt them
before [starting the dev server](#25-start-the-server) below.
