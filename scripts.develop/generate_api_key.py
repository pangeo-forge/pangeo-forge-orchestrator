import os
import sys
import uuid
from pathlib import Path

import yaml  # type: ignore

REPO_ROOT = Path(__file__).resolve().parent.parent


def main(app_name):
    creds_outpath = REPO_ROOT / f"secrets/config.{app_name}.yaml"

    key = {"PANGEO_FORGE_API_KEY": uuid.uuid4().hex}
    if os.path.exists(creds_outpath):
        with open(creds_outpath) as c:
            creds = yaml.safe_load(c)
    else:
        creds = {}

    with open(creds_outpath, "w") as out:
        creds["fastapi"] = key
        yaml.dump(creds, out)


if __name__ == "__main__":
    app_name = sys.argv[1]
    sys.exit(main(app_name))
