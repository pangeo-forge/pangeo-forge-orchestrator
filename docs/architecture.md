# Architecture

<html>
<style type="text/css">
    pre{ background-color: rgb(30, 30, 30); }
    .test{ color: rgb(113, 198, 177); }
    .deploy{ color: rgb(204, 118, 209); }
    .config{ color: rgb(170, 218, 250); }
</style>
<pre>
.
├── <span class="config">bakeries</span>
│   └──> This
├── <span class="deploy">dataflow-status-monitoring</span>
│   └──>
├── <span class="config">migrations</span>
│   └──>
├── pangeo_forge_orchestrator
│   └──>
├── <span class="deploy">scripts.deploy</span>
│   └──>
├── scripts.develop
│   └──>
├── <span class="config">secrets</span>
│   └──>
├── <span class="deploy">terraform</span>
│   └──>
├── <span class="test">tests</span>
│   └──>
├── <span class="deploy">Dockerfile</span> -> Builds the FastAPI container used on Heroku.
├── <span class="deploy">app.json</span>   -> Configures Heroku infrastructure.
├── <span class="test">docker-compose.yml</span> -> For running tests in the built container.
├── <span class="deploy">heroku.yml</span>        -> Defines Heroku container stack release + build process.
├── <span class="test">pyproject.toml</span> -> For local installs, used in testing.
├── <span class="deploy">requirements.txt</span> -> Pinned requirements, installed in Dockerfile.
├── <span class="test">setup.cfg</span> -> For local installs, used in testing.
└── <span class="test">setup.py</span> -> For local installs, used in testing.
</pre>
</html>
