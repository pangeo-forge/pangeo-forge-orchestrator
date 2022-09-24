# Architecture

A high-level representation of Pangeo Forge Cloud is provided below, illustrating relationships of its main components.

**Note**: In the diagram below, the _GitHub App_, _FastAPI_, and _Database_ components are all configured and/or deployed by `pangeo-forge-orchestrator`.

```mermaid
sequenceDiagram
    Feedstock Repo-->>GitHub App: event
    GitHub App-->>FastAPI: webhook
    FastAPI->>Database: records event
    FastAPI->>GitHub App: authenticates as
    GitHub App->>Feedstock Repo: to take action
    FastAPI->>Bakery: deploys jobs
    Bakery-->>FastAPI: reports job status
    FastAPI->>Database: records job status
    FastAPI->>GitHub App: authenticates as
    GitHub App->>Feedstock Repo: to report job status
    pangeo-forge.org-->>FastAPI: requests data
    FastAPI-->>Database: fetches data
    Database->>FastAPI: returns data
    FastAPI->>pangeo-forge.org: returns data
```
