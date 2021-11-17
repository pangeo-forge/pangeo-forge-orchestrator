import subprocess
from pathlib import Path

parent = Path(__file__).absolute().parent
cmd = ["uvicorn", "pangeo_forge_orchestrator.api:api", "--reload", f"--reload-dir={parent}"]
subprocess.run(cmd)
