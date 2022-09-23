# Architecture

## Instance-level configuration

- `bakeries/`
- `secrets/`
  - `config.${INSTANCE_NAME}.yaml`

## FastAPI Application

- `pangeo_forge_orchestrator/`

## Deployment

- `dataflow-status-monitoring/*`
- `terraform/*`
- `migrations/*`
- `Dockerfile`
- `requirements.txt`
- `heroku.yml`
- `app.json`
- `scripts.deploy/release.sh`
- `secrets/`
  - `dataflow-status-monitoring.json`
  - `dataflow-job-submission.json`
- `.sops.yaml`

## Testing

- `tests/`
- `setup.py`
- `setup.cfg`
- `pyproject.toml`
- `docker-compose.yml`

## Development

- `scripts.develop/*`
