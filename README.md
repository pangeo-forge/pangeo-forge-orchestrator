# Pangeo Forge Orchestrator

[![Tests](https://github.com/pangeo-forge/pangeo-forge-orchestrator/actions/workflows/main.yaml/badge.svg)](https://github.com/pangeo-forge/pangeo-forge-orchestrator/actions/workflows/main.yaml)
[![codecov](https://codecov.io/gh/pangeo-forge/pangeo-forge-orchestrator/branch/main/graph/badge.svg?token=ay8eJ6JUiX)](https://codecov.io/gh/pangeo-forge/pangeo-forge-orchestrator)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://github.com/pre-commit/pre-commit)
[![gitleaks badge](https://img.shields.io/badge/protected%20by-gitleaks-blue)](https://github.com/zricethezav/gitleaks-action)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![NSF Award 2026932](https://img.shields.io/badge/NSF-2026932-9cf)](https://www.nsf.gov/awardsearch/showAward?AWD_ID=2026932&HistoricalAwards=false)

This repo deploys the backend service for Pangeo Forge Cloud. It provides the data presented on
[https://pangeo-forge.org/](https://pangeo-forge.org/) and handles events for the
[`pangeo-forge` GitHub App](https://github.com/apps/pangeo-forge).

💡 **Note**: Most users of Pangeo Forge will not need to reference the code in this repo. You may be interested in:

- [What is Pangeo Forge?](https://pangeo-forge.readthedocs.io/en/latest/what_is_pangeo_forge.html)
- [Pangeo Forge Cloud **Core Concepts**](https://pangeo-forge.readthedocs.io/en/latest/pangeo_forge_cloud/core_concepts.html)
- [Pangeo Forge Cloud **Data Catalog**](https://pangeo-forge.org/catalog)
- [Pangeo Forge Cloud **Dashboard**](https://pangeo-forge.org/dashboard/feedstocks)
- [Recipe Contribution Docs](https://pangeo-forge.readthedocs.io/en/latest/pangeo_forge_cloud/recipe_contribution.html)

## API Documentation

Auto-generated API Documentation for

| Deployment  | API Docs                                  |
| ----------- | ----------------------------------------- |
| Prod API    | https://api.pangeo-forge.org/docs         |
| Staging API | https://api-staging.pangeo-forge.org/docs |

## Developer Documentation

- [Development Guide](/docs/development_guide.md)
- [Heroku](/docs/heroku.md)
- [Migrations](/docs/migrations.md)
- []
- [Testing](/docs/testing.md)
-
