#!/bin/bash

set -e

if [[ -z "${PANGEO_FORGE_DEPLOYMENT}" ]]; then
  echo "PANGEO_FORGE_DEPLOYMENT undefined, so this must be a review app..."
  echo "Review app injected env var \$HEROKU_APP_NAME=${HEROKU_APP_NAME}..."
  echo "Setting PANGEO_FORGE_DEPLOYMENT=\$HEROKU_APP_NAME..."
  export PANGEO_FORGE_DEPLOYMENT=$HEROKU_APP_NAME
fi

export TF_IN_AUTOMATION=true
# TODO: think about if all released deployments will maintain their own
# distinct dataflow-status-monitoring creds. For now, assuming they will.
# NOTE: we are replace all dashes in deployment name with underscores
export TF_CREDS="config/${PANGEO_FORGE_DEPLOYMENT//-/_}/secrets/dataflow-status-monitoring.json"
export GOOGLE_APPLICATION_CREDENTIALS="`pwd`/${TF_CREDS}"
export GET_GCP_PROJECT="import sys, json; print(json.load(sys.stdin)['project_id'].strip())"

echo "running database migration..."
python3.10 -m alembic upgrade head

echo "setting terraform env..."
# PANGEO_FORGE_DEPLOYMENT is the exact name of the GitHub App to release.
# For the persistent deployments (i.e. GitHub Apps) 'pangeo-forge' & 'pangeo-forge-staging',
# PANGEO_FORGE_DEPLOYMENT is 1:1 with TF_ENV. Each of these apps has its own dedicated terraform
# environment to prevent accidentally breaking its infrastructure during development.
# For ephemeral dev deployments, we use a single catchall TF_ENV, called 'dev'.
# Ephemeral dev deployments include both review apps (with names such as 'pforge-pr-80')
# and developers' local proxy apps (with names such as 'pforge-local-cisaacstern').
# Managing the infrastructure for all of these ephemeral apps within a single terraform environment
# reduces the amount of infra which needs to be spun up (and subsequently destroyed) during
# each development cycle. The tradeoff is that the release of one PR's review app could theoretically
# break *all* review app infrastructure. This would only happen, however, if a PR changes this release
# script, something in the `terraform` envs dir, or the reference hash for the `dataflow-status-monitoring`
# submodule. If we hit some version of this problem, we can reevaluate grouping all dev deployments under
# a single TF_ENV. Until then, this seems like a reasonable compromise between overhead & reliability.
export SET_TF_ENV="
import os;
deployment = os.environ['PANGEO_FORGE_DEPLOYMENT'];
if deployment not in ('pangeo-forge', 'pangeo-forge-staging'):
    print('dev')
else:
    print(deployment)
"
export TF_ENV=$(python3.10 -c "${SET_TF_ENV}")
echo "terraform env set to '${TF_ENV}'"

echo "setting aws config for kms access..."
aws configure set aws_access_key_id $AWS_ACCESS_KEY_ID
aws configure set aws_secret_access_key $AWS_SECRET_ACCESS_KEY

echo "decrypting app secrets..."
# For the persistent deployments 'pangeo-forge' & 'pangeo-forge-staging', APP_NAMES will always
# be a single-element array, in which the sole value is identical to TF_ENV.
# For dev deployments, APP_NAMES will be an n-element array containing as many review and/or
# local proxy configurations as are currently present.
export PARSE_APP_NAMES="
import os;
tf_env = os.environ['TF_ENV'];
if tf_env in ('pangeo-forge', 'pangeo-forge-staging'):
    apps = [tf_env.replace('-', '_')]
else:
    apps = [
        a
        for a in os.listdir('config')
        if (
            os.path.isdir(f'config/{a}')
            and 'secrets' in os.listdir(f'config/{a}')
            and 'github-app.yaml' in os.listdir(f'config/{a}/secrets')
        )
    ];
    apps = [a for a in apps if a not in ('pangeo_forge', 'pangeo_forge_staging')];
apps = ' '.join(apps);
print(apps)
"
# set this as an env var (rather than assigning it directly to `app_array`),
# because it is also used in the `GET_APPS_WITH_SECRETS` python command below.
export APP_NAMES=$(python3.10 -c "${PARSE_APP_NAMES}")

app_array=$APP_NAMES
for app in ${app_array[@]}; do
  echo "decrypting secrets for ${app}..."
  sops -d -i "./config/${app}/secrets/github-app.yaml"
done

echo "dynamically setting webhook secrets from app config..."
export GET_APPS_WITH_SECRETS="
import json, os, yaml;
apps_with_secrets = {};
for a in os.environ['APP_NAMES'].split():
    with open(f'./config/{a}/secrets/github-app.yaml') as f:
        secret = yaml.safe_load(f)['webhook_secret'].strip()
        apps_with_secrets.update({a: secret})
print(json.dumps(apps_with_secrets))
"
export APPS_WITH_SECRETS=$(python3.10 -c "${GET_APPS_WITH_SECRETS}")

echo "dynamically setting gcp project from service account keyfile..."
sops -d -i "./${TF_CREDS}"
export GCP_PROJECT=$(cat ./${TF_CREDS} | python3.10 -c "${GET_GCP_PROJECT}")

echo "running terraform for env '${TF_ENV}'..."
terraform -chdir='./terraform/'${TF_ENV} init
terraform -chdir='./terraform/'${TF_ENV} plan -out tfplan \
-var 'credentials_file=../../'${TF_CREDS} \
-var 'project='${GCP_PROJECT} \
-var 'apps_with_secrets='"${APPS_WITH_SECRETS}"
terraform -chdir='./terraform/'${TF_ENV} apply tfplan

echo "re-encrypting secrets..."
echo "re-encrypting terraform secrets..."
sops -e -i "./${TF_CREDS}"
for app in ${app_array[@]}; do
  echo "re-encrypting secrets for ${app}..."
  sops -e -i "./config/${app}/secrets/github-app.yaml"
done

echo "release complete!"
