# Note: Procfile is NOT run in test environment
release: python -m alembic upgrade head
web: gunicorn -w 3 -k uvicorn.workers.UvicornWorker pangeo_forge_orchestrator.api:app
