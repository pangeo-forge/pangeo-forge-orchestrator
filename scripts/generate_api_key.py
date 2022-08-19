import hashlib
import os
import sys
import uuid
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
CREDS_OUTPATH = REPO_ROOT / "secrets/config.dev.yaml"


def main():
    salt = uuid.uuid4().hex
    raw_key = uuid.uuid4().hex
    encrypted_key = hashlib.sha256(salt.encode() + raw_key.encode()).hexdigest()
    keys = {
        "ENCRYPTION_SALT": salt,
        "PANGEO_FORGE_API_KEY": raw_key,
        "ADMIN_API_KEY_SHA256": encrypted_key,
    }
    if os.path.exists(CREDS_OUTPATH):
        with open(CREDS_OUTPATH) as c:
            creds = yaml.safe_load(c)
    else:
        creds = {}

    with open(CREDS_OUTPATH, "w") as out:
        creds["fastapi"] = keys
        yaml.dump(creds, out)


if __name__ == "__main__":
    sys.exit(main())
