#!/bin/bash

set -e

# The first line of this script sets PANGEO_FORGE_DEPLOYMENT to itself, if it exists,
# but if it doesn't exist, PANGEO_FORGE_DEPLOYMENT is set to the value of HEROKU_APP_NAME.
# The latter case occurs only in the review app context. We use this method because review
# app names are dynaically generated based on the PR number and are therefore to cumbersome
# to set manually for each PR. More on this syntax in: https://stackoverflow.com/a/2013589.
export PANGEO_FORGE_DEPLOYMENT="${PANGEO_FORGE_DEPLOYMENT:=$HEROKU_APP_NAME}"
echo "PANGEO_FORGE_DEPLOYMENT set to ${PANGEO_FORGE_DEPLOYMENT}"

echo "decrypting secrets for deployment..."
bash ./scripts.deploy/sops.sh -d $PANGEO_FORGE_DEPLOYMENT

# NOTE: we are replace all dashes in deployment name with underscores
export DATAFLOW_CREDS="./config/${PANGEO_FORGE_DEPLOYMENT//-/_}/secrets/dataflow-job-submission.json"
gcloud auth activate-service-account --key-file=${DATAFLOW_CREDS}

cat ${DATAFLOW_CREDS} \
| python3.9 -c "import sys, json; print(json.load(sys.stdin)['project_id'].strip())" \
| xargs -I{} gcloud config set project {}

export GOOGLE_APPLICATION_CREDENTIALS=${DATAFLOW_CREDS}

# while deterministic from PANGEO_FORGE_DEPLOYMENT in this context, this is its own distinct
# variable (rather than being derived from PANGEO_FORGE_DEPLOYMENT in the application) to
# provide greater flexibility in other contexts, including testing.
export ORCHESTRATOR_CONFIG_FILE="./config/${PANGEO_FORGE_DEPLOYMENT//-/_}/config.py"

gunicorn -w 2 -t 300 -k uvicorn.workers.UvicornWorker pangeo_forge_orchestrator.api:app
