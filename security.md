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
