#!/bin/bash

set -e
export TF_IN_AUTOMATION=true
export TF_DIR="./dataflow-status-monitoring/terraform"
export TF_CREDS="secrets/dataflow-status-monitoring.json"
export GOOGLE_APPLICATION_CREDENTIALS="`pwd`/${TF_CREDS}"
export GET_WEBHOOK_SECRET="import sys, yaml; print(yaml.safe_load(sys.stdin)['github_app']['webhook_secret'].strip())"
export GET_GCP_PROJECT="import sys, json; print(json.load(sys.stdin)['project_id'].strip())"

echo "running database migration..."
python3.9 -m alembic upgrade head

echo "decrypting app secrets..."
export PARSE_APP_NAMES="
import os;
apps = [f.split('.')[1] for f in os.listdir('secrets') if f.startswith('config')];
apps = ' '.join(apps);
print(apps)
"
app_array=$(python3.9 -c "${PARSE_APP_NAMES}")
for app in ${app_array[@]}; do
  # sops -d -i "./secrets/config.${app}.yaml"
  echo $app
done
echo "dynamically setting webhook secrets from app config..."
export GET_APPS_WITH_SECRETS="
import json, os, yaml;
apps = [f.split('.')[1] for f in os.listdir('secrets') if f.startswith('config')];
apps_with_secrets = {};
for a in apps:
    with open(f'secrets/config.{a}.yaml') as f:
        secret = yaml.safe_load(f)['github_app']['webhook_secret'].strip()
        apps_with_secrets.update({a: secret})
print(json.dumps(apps_with_secrets))
"
echo $(python3.9 -c "${GET_APPS_WITH_SECRETS}")
exit
export APP_0_SECRET=
export APP_1_SECRET=$(cat ./secrets/config.${APP_1}.yaml | python3.9 -c "${GET_WEBHOOK_SECRET}")
# TODO: set this dynamically, maybe with a python -c list comprehension?
export APPS_WITH_SECRETS="{\"${APP_0}\":\"${APP_0_SECRET}\",\"${APP_1}\":\"${APP_1_SECRET}\"}"

echo "dynamically setting gcp project from service account keyfile..."
sops -d -i "./${TF_CREDS}"
export GCP_PROJECT=$(cat ./${TF_CREDS} | python3.9 -c "${GET_GCP_PROJECT}")

echo "running terraform..."
terraform -chdir=${TF_DIR} init
terraform -chdir=${TF_DIR} plan -out tfplan \
-var 'credentials_file=../../'${TF_CREDS} \
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

sops -e -i "./${TF_CREDS}"
# TODO: do this in a loop
sops -e -i "./secrets/config.${APP_0}.yaml"
sops -e -i "./secrets/config.${APP_1}.yaml"

echo "release complete!"
