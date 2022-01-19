# only using one worker for now (-w 1) to ensure that there is only one sqlite database
web: gunicorn -w 1 -k uvicorn.workers.UvicornWorker pangeo_forge_orchestrator.api:app
