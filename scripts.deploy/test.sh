#!/bin/bash

# This test entrypoint is for use with docker-compose.yml in repo root. Some notes:
# - Sleep at start to allow postgres enought time to start. There are some more involved
#   solutions to this problem at https://docs.docker.com/compose/startup-order/, but because
#   this is just for testing, I think this should be enough, and is much lighter weight.
# - The commands following sleep combine the `release` and `web` directives from `heroku.yml`,
#   with the following small differences:
#   - docker-compose spec requires double $$ for string interpolation (vs. single $)
#   - Only running one gunicorn worker here (as opposed to 4 in production). Specifying more
#     than 1 worker fails in this context.
#   - We bind to 0.0.0.0 (as opposed to default 127.0.0.1) to make port binding to host work

set -e

sleep 1
python3.9 -m alembic upgrade head

# these are to allow sops decryption of secrets via aws kms
aws configure set aws_access_key_id $AWS_ACCESS_KEY_ID
aws configure set aws_secret_access_key $AWS_SECRET_ACCESS_KEY

/bin/bash ./scripts.deploy/sops.sh -d ${PANGEO_FORGE_DEPLOYMENT}

export DATAFLOW_CREDS=./config/${PANGEO_FORGE_DEPLOYMENT//-/_}/secrets/dataflow-job-submission.json
gcloud auth activate-service-account --key-file=${DATAFLOW_CREDS}

cat ${DATAFLOW_CREDS} \
| python3.9 -c "import sys, json; print(json.load(sys.stdin)['project_id'].strip())" \
| xargs -I{} gcloud config set project {}

export GOOGLE_APPLICATION_CREDENTIALS=${DATAFLOW_CREDS}

export ORCHESTRATOR_CONFIG_FILE=./config/${PANGEO_FORGE_DEPLOYMENT//-/_}/config.py

gunicorn -w 1 -t 300 -k uvicorn.workers.UvicornWorker pangeo_forge_orchestrator.api:app -b 0.0.0.0:8000
