# Project Context and Existing-Project Onboarding

## 1. When to Use

Run Project Onboarding first when:

- entering an unfamiliar repository;
- maintaining several similar projects;
- work spans sessions or is long-running;
- preparing to commit, push, deploy, restart, or write data;
- historical documents may disagree with current source.

A simple one-time read-only question may omit a Project Profile, but still identify the current repository and branch.

## 2. Onboarding Commands

```bash
python3 scripts/cp-runtime.py project-onboard \
  --repo-path /path/to/repo \
  --project-id logistics-system \
  --project-name "AI Logistics Management System"
```

Use a custom directory outside the repository:

```bash
python3 scripts/cp-runtime.py project-onboard \
  --repo-path /path/to/repo \
  --context-dir /secure/external/context/logistics-system
```

## 3. Automatic Detection Scope

The tool reads only:

- Git root, branch, HEAD, remote, and workspace state;
- root-level build markers;
- first-level module markers;
- bounded framework or script declarations in files such as `pom.xml` and `package.json`.

It does not:

- scan all source deeply;
- build, test, or start the application;
- access networks, databases, or production;
- read `.env` and store credentials;
- label heuristic inference as confirmed.

## 4. Review the Profile

After first generation, check:

1. `identity.repo_path` and `remote_origin`.
2. Missing primary technology under `technology`.
3. `confidence` for each `entrypoints` item.
4. Environment, data sensitivity, and ownership under `boundaries`.
5. Whether actual evidence resolved any `unknowns`.
6. Whether `prohibited_paths` covers dependencies, artifacts, and sensitive directories.

## 5. Refresh and Validate

```bash
python3 scripts/cp-runtime.py project-refresh \
  --profile /path/to/project-profile.json
```

```bash
python3 scripts/cp-runtime.py project-validate \
  --profile /path/to/project-profile.json \
  --repo-path /path/to/repo
```

Refresh primarily updates the Git baseline in Project State. The stable Project Profile binding hash changes only when project identity or governance boundaries change.

## 6. Project Isolation

Every project needs its own project ID and directory. Do not:

- copy Project A's Profile to Project B;
- reuse another project's Approval;
- put another project's APIs, schemas, credentials, or conclusions into current Project Memory;
- switch repository roots within one task state;
- rely on identical project names while ignoring remote and path validation.
