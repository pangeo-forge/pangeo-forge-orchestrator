## Local Testing

Migrations are not used for local testing with SQLite. To setup local testing, simply define the `DATABASE_URL` environment variable

```bash
export DATABASE_URL=sqlite:///`pwd`/database.sqlite
```

and then invoke the tests

```bash
pytest -vx
```

> If no file exists at the `DATABASE_URL`, a new SQLite database file will be automatically created for the test session and populated
> with tables based on `pangeo_forge_orchestrator.models`. If a file already exists at the at the `DATABASE_URL`, it will be updated
> to refect the tables defined by `pangeo_forge_orchestrator.models`. Note that `.sqlite` files are excluded by `.gitignore`, so you don't
> need to worry about the database file appearing in your commit. **You may, however, need to manually `rm database.sqlite` in between test
> sessions.**

Our Heroku CI tests (along with the production API) run with a Postgres server. Postgres implements certain features not present in SQLite.
As such, after your local tests passes against the SQLite database, you may want to test against a local Postgres server as a final check.
To do so:

1.  Install https://postgresapp.com
2.  Start the database using the app
3.  Run `echo "CREATE DATABASE test_db;" | psql` to create a database
4.  Set `export DATABASE_URL=postgresql://localhost/test_db`

        > If you are working on a PR that includes changes to `pangeo_forge_orchestrator.models`, you may need to generate a new alembic

    migration version before proceeding to Step 4. Refer to **Running Migrations** above for details.

5.  Run `python -m alembic upgrade head` to execute alembic migration against the new Postgres `DATABASE_URL`
6.  `pytest -vx`

- [7 Before merge: automated testing]()
  - [7.1 Mocking payloads]()
  - [7.2 Local run]()
    - [7.2.1 sqlite]()
    - [7.3.2 postgres]()
  - [7.3 Containerized run]()
    - [7.3.1 Starting the containerized services]()
    - [7.3.2 Testing on the containerized services]()
