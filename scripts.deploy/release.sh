#!/bin/sh

set -e
# TODO: it would be good to loop over files in secrets, and grap these values dynamically
# from filenames that startwith config. could do this pretty easily with python -c
# TODO: add staging and prod config here (if looping, won't need to do that manually)
export APP_0="pforge-local-cisaacstern"
export APP_1="pforge-pr-80"

export TF_IN_AUTOMATION=true
export TF_DIR="./dataflow-status-monitoring/terraform"
export TF_CREDS="./secrets/dataflow-status-monitoring.json"
export TF_STATE="./secrets/terraform.tfstate"
export GET_WEBHOOK_SECRET="import sys, yaml; print(yaml.safe_load(sys.stdin)['github_app']['webhook_secret'].strip())"
export GET_GCP_PROJECT="import sys, json; print(json.load(sys.stdin)['project_id'].strip())"

echo "running database migration..."
python3.9 -m alembic upgrade head

echo "dynamically setting webhook secrets from app config..."
# TODO: do this dynamically with a loop
sops -d -i "./secrets/config.${APP_0}.yaml"
sops -d -i "./secrets/config.${APP_1}.yaml"
export APP_0_SECRET=$(cat ./secrets/config.${APP_0}.yaml | python3.9 -c "${GET_WEBHOOK_SECRET}")
export APP_1_SECRET=$(cat ./secrets/config.${APP_1}.yaml | python3.9 -c "${GET_WEBHOOK_SECRET}")
# TODO: set this dynamically, maybe with a python -c list comprehension?
export APPS_WITH_SECRETS="{\"${APP_0}\":\"${APP_0_SECRET}\",\"${APP_1}\":\"${APP_1_SECRET}\"}"

echo "dynamically setting gcp project from service account keyfile..."
sops -d -i ${TF_CREDS}
export GCP_PROJECT=$(cat ./${TF_CREDS} | python3.9 -c "${GET_GCP_PROJECT}")

echo "running terraform..."
sops -d -i ${TF_STATE}
terraform -chdir=${TF_DIR} init -backend-config 'path=../.'${TF_STATE}
terraform -chdir=${TF_DIR} plan -out tfplan \
-var 'credentials_file=../.'${TF_CREDS} \
-var 'project='${GCP_PROJECT} \
-var 'apps_with_secrets='${APPS_WITH_SECRETS}
terraform -chdir=${TF_DIR} apply tfplan

echo "re-encrypting secrets..."
# if AGE_PUBLIC_KEY is set, include it in encryption recipients.
# this is never set in a real release, but is useful for working with this script locally.
if [[ -z "${AGE_PUBLIC_KEY}" ]]; then
    export SOPS_AGE_RECIPIENTS=$(cat age-recipients.txt)
else
    export SOPS_AGE_RECIPIENTS=$(cat age-recipients.txt),${AGE_PUBLIC_KEY}
fi

sops -e -i ${TF_CREDS}
sops -e -i ${TF_STATE}
# TODO: do this in a loop
sops -e -i "./secrets/config.${APP_0}.yaml"
sops -e -i "./secrets/config.${APP_1}.yaml"

echo "release complete!"
