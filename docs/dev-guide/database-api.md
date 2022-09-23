## Generating credentials

Before starting work on your PR, you will need a local deployment of the application to work with. In
order to run this deployment, you will need to generate credentials for FastAPI.

Each deployment requires FastAPI credentials. These are the creds that are used to authorize protected
actions on such as creating, patching, and deleting entries in the database.

To generate these credentials for the `local` deployment, from the repo root, run:

```console
$ python3 scripts.develop/generate_api_key.py local
```

If you look at `secrets/config.local.yaml` now, you should see that creds have been added to it under the
`fastapi` heading.

## 2.3 Database

You will not be able to start your `local` dev server without first setting the `DATABASE_URL` env variable,
which tells the application where to connect to the database.

By far the easiest way to do this is by using a sqlite database, as follows:

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

> **TODO**: Move postgres setup documentation from top level README to here? Or otherwise link to it.

## 3.3 Initializing the database

Before triggering a webhook from a simulated feedstock, the app's database needs to know that that the
feedstock repo(s) exist. If you navigate to http://localhost:8000/feedstocks now, you should see just an
empty list:

```
[]
```

To add your mock feedstock repo(s) to the database, from the repo root in a new
terminal window, run:

```console
$ python3 scripts/initialize_database.py http://localhost:8000 cisaacstern/mock-dataset-feedstock
```

but replace `cisaacstern/mock-dataset-feedstock` with the name of (one of) your mock feedstock repos.

> If you've created more than one mock feedstock repo (i.e., a dataset feedstock and a staged-recipes),
> you can call this script once for each one.

Now, when you navigate to http://localhost:8000/feedstocks, you should see the feedstock(s) you just added
to the database listed:

```
[{"spec":"cisaacstern/mock-dataset-feedstock","provider":"github","id":1}]
```

And there's one more entry that `scripts/initialize_database.py` added to the database for us. At
http://localhost:8000/bakeries, you should see metadata for a "local-test-bakery":

```
[{"region":"local","name":"local-test-bakery","description":"A great bakery.","id":1}]
```

Almost all of the actions that the FastAPI application will take against the database will require
these entries to be present in the database, which is why this step has been automated. In the course
of development, however, you may want to further customize and/or modify data in the database. In that
case, it's recommended to review the contents of `scripts/initialize_database.py`, which demonstrate
how to edit the database using Python's `requests` library. This code can also be translated to be
run from the command line with `curl`. And remember, the full API documentation is available at
http://localhost:8000/docs.
