# nutriscore

A minimal Python web app exposing a single REST endpoint.

## Requirements

- [uv](https://docs.astral.sh/uv/)

## Setup

```bash
uv sync
```

## Run

```bash
uv run uvicorn nutriscore.main:app --reload --app-dir src
```

Then call the endpoint:

```bash
curl http://127.0.0.1:8000/hello
# {"message":"hello world"}
```

## Test

```bash
uv run pytest
```
