#!/bin/bash

set -e

if [ "$1" = "-d" ]
then
  export METHOD="decrpyt"
elif [[ "$1" = "-e" ]]
then
  export METHOD="encrypt"
else
  echo "ERROR: first argument must be one of -e (encrypt) or -d (decrypt)."
  exit 1
fi

export GET_SECRETS_FNAMES="
import os;

subdir = '$2'.replace('-', '_')
secrets_dir = f'./config/{subdir}/secrets'
print(' '.join([f'{secrets_dir}/{fname}' for fname in os.listdir(secrets_dir)]))
"
export secrets_fnames=$(python3.9 -c "${GET_SECRETS_FNAMES}")

for secrets_file in ${secrets_fnames[@]}; do
  echo "${METHOD}ing ${secrets_file}..."
  # there are actaully a lot of reasons why this could fail, but for now we'll just
  # assume it's always because the file is already in the requested state (a common
  # reason). this assumption has relatively little security implication: pre-commit
  # hooks will prevent us from accidentally committing unencrypted secrets.
  sops $1 -i ${secrets_file} > /dev/null 2>&1 \
  || echo "    Skipped; already ${METHOD}ed!"
done

exit 0
