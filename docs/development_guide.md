# Development Guide

## Install

For a development installation of `pangeo-forge-orchestrator`, start by cloning the repository.

Next, start a new `conda` environment with Python >= 3.8 and < 3.10.

Finally, from the repo root `git checkout` whichever branch you plan to develop on, then run

```bash
pip install -e '.[dev]'
```
to install the Python package, CLI entrypoint, and all dev dependencies.

## Start a local API dev server

In a new, empty directory outside of the project repo, activate the `conda` environment in which `pangeo-forge-orchestrator` is installed.
Then run

```bash
uvicorn pangeo_forge_orchestrator.api:api
```
to start an API development server.

> This command will also create a new `database.db` sqlite database file in your current working directory and populate that database with
blank tables for all models defined in the `MODELS` dictionary defined in `pangeo_forge_orchestrator.models`.

Calling `uvicorn --help` provides various options you can add to this command. Two worth noting:

- **`--reload`**: Enables hot reloads. Because our `uvicorn` process is not running in the package repository, enabling hot
reloads requires specifying the package repository path via the `--reload-dir` option. Enabling hot reloading might therefore look like
    ```bash
    uvicorn pangeo_forge_orchestrator.api:api --reload --reload-dir=$PFO_REPO_PATH
    ```
    where `PFO_REPO_PATH` is an environment variable pointing to the absolute path for `~/pangeo-forge-orchestrator/pangeo_forge_orchestrator/`.
- **`--port`**: The API server starts at `http://127.0.0.1:8000` by default. If your local port `8000` is occupied you can pass an alternate port number here.

## Checkout the API in a browser

> In what follows, we will assume your local API is running at `http://127.0.0.1:8000`. If you selected an alternate port, adjust the below URLs accordingly.

With the local API server running, you may now review the auto-generated API documentation by navigating to [http://127.0.0.1:8000/docs/](http://127.0.0.1:8000/docs/) in your browser. (The same documentation in a different style is also available at [http://127.0.0.1:8000/redoc/](http://127.0.0.1:8000/redoc/).)

For any given API endpoint (i.e., route) described in the documentation, you will note that navigating to that endpoint in the browser shows simply an empty list. For example, the browser just renders `[]` when we navigate to [http://127.0.0.1:8000/recipe_runs/](http://127.0.0.1:8000/recipe_runs/).

> If you do not see an empty list at this endpoint, that's likely because the directory your API is running in already had a sqlite file called `database.db` in it when the server started. This is an easy oversight to make, if you are starting and stopping servers in the same directory during a development session, given that the server does not delete the sqlite file when it is stopped.

## Interfaces

To perform any of the create, read, update, and delete (CRUD) operations on our database, we can choose whether to interface via the command line interface (CLI) or the Python client. Both of these entrypoints provide the same functionality and cooresponding functions have the same name in both interfaces.

### Client basics

To initialize a client for your local API server, execute

```python
>>> from pangeo_forge_orchestrator.client import Client

>>> client = Client(base_url="http://127.0.0.1:8000")
```
in your Python interpreter of choice.

### CLI basics

To get started with the CLI, make sure the `conda` environment in which `pangeo-forge-orchestrator` is installed is activated, and run

```bash
pangeo-forge database --help
```
to return a top-level listing of the CRUD function names. For each of the listed functions, similarly calling

```bash
pangeo-forge database $FUNC_NAME --help
```
will return a description of the arguments and/or options supported by the function.

To use any of these functions, the CLI will need to know the URL where the API server can be found. We communicate this by
setting the `PANGEO_FORGE_DATABASE_URL` environment variable:
```bash
export PANGEO_FORGE_DATABASE_URL='http://127.0.0.1:8000'
```

## CRUD operations

### Create

#### With client

Creating entries in a database table with many required fields, due to its relative verboseness, is likely easiest via the Python client.
Here's how to create an entry in the `recipe_run` table, using the `client` defined in the previous section.

First we inspect the creation schema demonstrated in the API documentation.
For the `/recipe_runs/` endpoint, the API documentation's example JSON looks like this:

```json
{
  "recipe_id": "string",
  "run_date": "2021-12-07T23:52:08.336Z",
  "bakery_id": 0,
  "feedstock_id": 0,
  "commit": "string",
  "version": "string",
  "status": "string",
  "path": "string",
  "message": "string"
}
```

Creating and posting such a request with the Python client is therefore as simple as:

```python

>>> json = {
  "recipe_id": "my-recipe-id",
  "run_date": "2021-12-07T23:52:08.336Z",
  "bakery_id": 1,  # Note that `bakery_id` and `feedstock_id` are placeholder fields
  "feedstock_id": 1,  # which will eventually link to other tables in the database
  "commit": "abcdefg1234567",
  "version": "1.0",
  "status": "complete",
  "path": "/path-to-dataset.zarr",
  "message": "An optional message.",
}
>>> response = client.post("/recipe_runs/", json=json)
>>> response.status_code
200
>>> response.json()
{'recipe_id': 'my-recipe-id',
 'run_date': '2021-12-07T23:52:08.336000',
 'bakery_id': 1,
 'feedstock_id': 1,
 'commit': 'abcdefg1234567',
 'version': '1.0',
 'status': 'complete',
 'path': '/path-to-dataset.zarr',
 'message': 'An optional message.',
 'id': 1}
```

Note that the addition of the `id` field in the API's response tells us the index of the entry in the database.

#### From CLI

While the length of this particular command may encourage sticking to the Python client for create requests, it's worth
noting that POST is also supported from the CLI. To create a second entry in the `recipe_run` table from the CLI, we run:

```console
$ pangeo-forge database post "/recipe_runs/" '{"recipe_id": "the-second-recipe-id", "run_date": "2021-12-07T23:52:08.336Z", "bakery_id": 1, "feedstock_id": 1, "commit": "abcdefg1234567", "version": "1.0", "status": "In progress", "path": "/path-to-second-dataset.zarr"}'

{'recipe_id': 'the-second-recipe-id', 'run_date': '2021-12-07T23:52:08.336000', 'bakery_id': 1, 'feedstock_id': 1, 'commit': 'abcdefg1234567', 'version': '1.0', 'status': 'In progress', 'path': '/path-to-second-dataset.zarr', 'message': None, 'id': 2}
```
The `response.json()` dictionary echoed to stdout is the entry as it now appears in the database.
(Our request omitted the optional `'message'` field, therefore it is returned from the database as `None`.
This is the second entry we've created in the table, therefore its `'id'` is `2`.)

### Read

#### With client

Now that we have posted some data to our table, we can read back that whole table with:

```python
>>> client.get("/recipe_runs/").json()
[{'recipe_id': 'my-recipe-id',
  'run_date': '2021-12-07T23:52:08.336000',
  'bakery_id': 1,
  'feedstock_id': 1,
  'commit': 'abcdefg1234567',
  'version': '1.0',
  'status': 'complete',
  'path': '/path-to-dataset.zarr',
  'message': 'An optional message.',
  'id': 1},
 {'recipe_id': 'the-second-recipe-id',
  'run_date': '2021-12-07T23:52:08.336000',
  'bakery_id': 1,
  'feedstock_id': 1,
  'commit': 'abcdefg1234567',
  'version': '1.0',
  'status': 'In progress',
  'path': '/path-to-second-dataset.zarr',
  'message': None,
  'id': 2}]
```

Or, if we just want to select a single entry from the table, we can append the `id` of that entry to
the path passed to the same `client.get` request:

```python
>>> client.get("/recipe_runs/1").json()
{'recipe_id': 'my-recipe-id',
 'run_date': '2021-12-07T23:52:08.336000',
 'bakery_id': 1,
 'feedstock_id': 1,
 'commit': 'abcdefg1234567',
 'version': '1.0',
 'status': 'complete',
 'path': '/path-to-dataset.zarr',
 'message': 'An optional message.',
 'id': 1}
```

#### From CLI

The same function can be performed from the CLI. For a list of all entries in the table:

```console
$ pangeo-forge database get "/recipe_runs/"

[{'recipe_id': 'my-recipe-id', 'run_date': '2021-12-07T23:52:08.336000', 'bakery_id': 1, 'feedstock_id': 1, 'commit': 'abcdefg1234567', 'version': '1.0', 'status': 'complete', 'path': '/path-to-dataset.zarr', 'message': 'An optional message.', 'id': 1}, {'recipe_id': 'the-second-recipe-id', 'run_date': '2021-12-07T23:52:08.336000', 'bakery_id': 1, 'feedstock_id': 1, 'commit': 'abcdefg1234567', 'version': '1.0', 'status': 'In progress', 'path': '/path-to-second-dataset.zarr', 'message': None, 'id': 2}]
```

Or, for just a single entry, append its `id` to the request path:
```console
$ pangeo-forge database get "/recipe_runs/1"

{'recipe_id': 'my-recipe-id', 'run_date': '2021-12-07T23:52:08.336000', 'bakery_id': 1, 'feedstock_id': 1, 'commit': 'abcdefg1234567', 'version': '1.0', 'status': 'complete', 'path': '/path-to-dataset.zarr', 'message': 'An optional message.', 'id': 1}
```

### Update

#### With client

Let's say we want to change the `recipe_id` field of the first `recipe_run` table entry. Currently, it's assigned as:

```python
>>> client.get("/recipe_runs/1").json()["recipe_id"]
'my-recipe-id'
```
We can use the client's `patch` method to change it, as follows:
```python
>>> client.patch("/recipe_runs/1", json=dict(recipe_id="corrected-recipe-id"))
<Response [200]>
>>> client.get("/recipe_runs/1").json()["recipe_id"]
'corrected-recipe-id'
```

The dictionary passed to `client.patch` is not limited to one field, as shown here; it can contain as many fields as you would like.

#### From CLI

The CLI interface for `patch` is almost identical:

```console
$ pangeo-forge database patch "/recipe_runs/1" '{"recipe_id": "fixed-twice-id"}'

{'recipe_id': 'fixed-twice-id', 'run_date': '2021-12-07T23:52:08.336000', 'bakery_id': 1, 'feedstock_id': 1, 'commit': 'abcdefg1234567', 'version': '1.0', 'status': 'complete', 'path': '/path-to-dataset.zarr', 'message': 'An optional message.', 'id': 1}
```


### Delete

#### With client

To delete an entry with the client, simply pass its `id`-terminated endpoint to `client.delete`:

```python
>>> client.delete("/recipe_runs/1")
<Response [200]>
>>> client.get("/recipe_runs/1").json()
{'detail': 'RecipeRun not found'}
```

#### From CLI

The CLI delete interface takes the same argument as the client. Simply pass it an `id`-terminated endpoint:

```console
$ pangeo-forge database delete "/recipe_runs/2"
{'ok': True}
$ pangeo-forge database get "/recipe_runs/2"
{'detail': 'RecipeRun not found'}
```
