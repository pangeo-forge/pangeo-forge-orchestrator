# REST API Spec

This is the spec for package version version **{{ env.config.version }}**,
exported from FastAPI in `conf.py` as follows

```python
import yaml
from pangeo_forge_orchestrator.api import api

api_spec = api.openapi()
with open("openapi.yaml", mode='w') as fp:
    yaml.dump(api_spec, fp)
```

```{eval-rst}
.. openapi:: openapi.yaml
```
