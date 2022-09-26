# Application Security

Security is currently implemented as API-key based authorization / authentication.

## Authentication

Clients authenticate by providing their API key in the `X-API-Key` HTTP header.
The configuration is based loosely on https://github.com/mrtolkien/fastapi_simple_security.

### Key Storage

The API keys are UUID4 values encoded as hex strings.

### Creating New Keys

### Updating Keys

There is currently no way to update keys (e.g. deactivating) via the API.
_This needs to be implemented._

## Authorization

There are currently three levels of authorization in the app

- _Unauthenticated Access_ - only GET operations
- _Authenticated Access_ - anyone with a valid api key can POST, UPDATE, DELETE
- _Admin Access_ - if your API key has the `is_admin` flag set to true, you have
  and extra special power: creating new API keys

Moving forward, we will likely need to make this more fine-grained.
In particular, we may wish to associate API keys with bakeries and / or users,
and restrict permissions based on these properties.

## TODO

- Implement admin interface for updating / deactivating keys
- Implement key expiry policies
- Link keys to specific users and / or bakeries (i.e. service account)
- Add a "comment" field to the api keys table to remember ourselves what a particular
  key was created for.
