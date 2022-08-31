#!/bin/sh

export APP_CONFIG="./secrets/config.${PANGEO_FORGE_DEPLOYMENT}.yaml"
export TF_IN_AUTOMATION=true
export TF_DIR="./dataflow-status-monitoring/terraform"
export TF_CREDS="./secrets/dataflow-status-monitoring.json"
export TF_STATE="./secrets/terraform.tfstate"
export GET_APP_NAME="import sys, yaml; print(yaml.safe_load(sys.stdin)['github_app']['app_name'].strip())"
export GET_WEBHOOK_SECRET="import sys, yaml; print(yaml.safe_load(sys.stdin)['github_app']['webhook_secret'].strip())"
export GET_GCP_PROJECT="import sys, json; print(json.load(sys.stdin)['project_id'].strip())"

echo "running database migration..."
python3.9 -m alembic upgrade head

echo "dynamically setting app name and webhook secret from app config..."
sops -d -i ${APP_CONFIG}
export APP_NAME=$(cat ${APP_CONFIG} | python3.9 -c "${GET_APP_NAME}")
export WEBHOOK_SECRET=$(cat ${APP_CONFIG} | python3.9 -c "${GET_WEBHOOK_SECRET}")

echo "dynamically setting gcp project from service account keyfile..."
sops -d -i ${TF_CREDS}
export GCP_PROJECT=$(cat ./${TF_CREDS} | python3.9 -c "${GET_GCP_PROJECT}")

echo "running terraform..."
sops -d -i ${TF_STATE}
terraform -chdir=${TF_DIR} init -backend-config 'path=../.'${TF_STATE}
terraform -chdir=${TF_DIR} plan -out tfplan \
-var 'credentials_file=../.'${TF_CREDS} \
-var 'project='${GCP_PROJECT} \
-var 'app_name='${APP_NAME} \
-var 'webhook_secret='${WEBHOOK_SECRET}
terraform -chdir=${TF_DIR} apply tfplan

echo "release complete!"
