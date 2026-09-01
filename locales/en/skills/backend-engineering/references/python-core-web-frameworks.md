# Python Project Identification, Layers, and Web Frameworks

## 1. Identify the Project Role and Version

Python may support a complete business backend, API service, microservice, administration backend, AI model service, RAG, asynchronous worker, data pipeline, file or video processing, GPU inference, or automation script.

Do not apply an AI-worker design to an ordinary business API, and do not run model inference or long video tasks through synchronous web-request handling.

Identify the environment in this order:

1. Versions and frameworks explicitly stated by the current task.
2. The project context card.
3. `pyproject.toml`, `requirements.txt`, `Pipfile`, `poetry.lock`, and `uv.lock`.
4. Dockerfile, CI/CD configuration, and startup scripts.
5. The actual virtual environment, runtime, and startup logs.

Confirm:

- Python version and syntax target;
- frameworks such as FastAPI, Django, Flask, Starlette, Sanic, or Litestar;
- synchronous or asynchronous database drivers;
- runtime configuration such as Uvicorn, Gunicorn, or Hypercorn;
- task systems such as Celery, Dramatiq, or RQ;
- package management, type checking, linting, and testing systems.

Never invent lifecycle, configuration, or extension capabilities that a framework does not provide.

---

## 2. Business Backend Layers

When Python is a complete business backend, prefer clear boundaries:

- API or Router: requests, parameters, authentication results, basic validation, and responses.
- Schema or DTO: input/output models and separation between internal and external models.
- Application or Service: business orchestration, transactions, state, idempotency, and authorization.
- Domain: core rules for complex business systems.
- Repository or DAO: queries, persistence, locks, and batching.
- Model or Entity: persistence models.
- Infrastructure or Integration: middleware, storage, and external services.

Do not:

- put complex business logic, long transactions, extensive ORM work, or long model tasks in routers;
- scatter ORM queries across routers, utility classes, and task code;
- expose ORM entities directly through external APIs without boundaries;
- force complex DDD into a simple project.

---

## 3. FastAPI and Django

### 3.1 FastAPI

Proactively check:

- router, Pydantic schema, dependency injection, and database-session lifecycles;
- separation of request and response models;
- consistent exception handling;
- repeated heavy work in middleware;
- OpenAPI, CORS, upload-size limits, and exposure of sensitive endpoints;
- blocking calls inside `async def`;
- accidental mixing of synchronous and asynchronous database drivers;
- correct initialization and closure of lifecycle resources.

`BackgroundTasks` is not a replacement for a reliable task queue when handling long tasks, tasks requiring retry or recovery, video processing, model inference, or resource-intensive work.

### 3.2 Django

Proactively check:

- responsibility boundaries among views, serializers, services, and models;
- QuerySet N+1 access, `select_related`, and `prefetch_related`;
- middleware, signals, migrations, administration, authorization, and object-level permissions;
- transaction boundaries and Celery use of the ORM;
- static-file and uploaded-file security.

Do not hide complex core business logic inside model `save()`, signals, or serializers; such implicit side effects are difficult to discover and control.

---
