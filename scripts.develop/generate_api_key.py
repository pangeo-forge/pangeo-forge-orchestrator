import hashlib
import os
import sys
import uuid
from pathlib import Path

import yaml  # type: ignore

REPO_ROOT = Path(__file__).resolve().parent.parent


def main(app_name):
    creds_outpath = REPO_ROOT / f"secrets/config.{app_name}.yaml"

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
    app_name = sys.argv[1]
    sys.exit(main(app_name))
