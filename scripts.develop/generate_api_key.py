import hashlib
import os
import sys
import uuid
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent


def main(deployment):
    creds_outpath = REPO_ROOT / f"secrets/config.{deployment}.yaml"

    salt = uuid.uuid4().hex
    raw_key = uuid.uuid4().hex
    encrypted_key = hashlib.sha256(salt.encode() + raw_key.encode()).hexdigest()
    keys = {
        "ENCRYPTION_SALT": salt,
        "PANGEO_FORGE_API_KEY": raw_key,
        "ADMIN_API_KEY_SHA256": encrypted_key,
    }
    if os.path.exists(creds_outpath):
        with open(creds_outpath) as c:
            creds = yaml.safe_load(c)
    else:
        creds = {}

    with open(creds_outpath, "w") as out:
        creds["fastapi"] = keys
        yaml.dump(creds, out)


if __name__ == "__main__":
    deployment = sys.argv[1]
    allowed_deployments = ("prod", "staging", "review", "local")
    if deployment not in allowed_deployments:
        raise ValueError(f"{deployment =} not in {allowed_deployments =}.")
    sys.exit(main(deployment))
