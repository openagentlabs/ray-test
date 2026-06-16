# iam.svc server

gRPC IAM service backed by DynamoDB. Configure `[dynamodb.tables]` in `app_config.toml` with names from `terraform output` in `infra/aws_tf`.

## Regenerate protobuf (Python)

```bash
cd iam.svc/server
python3 -m venv .venv && .venv/bin/pip install "grpcio-tools>=1.80"
PROTO_INC=$(.venv/bin/python -c "import grpc_tools, pathlib; print(pathlib.Path(grpc_tools.__file__).parent/'_proto')")
mkdir -p src/iam/v1
.venv/bin/python -m grpc_tools.protoc -Iproto -I"$PROTO_INC" --python_out=src --grpc_python_out=src proto/iam/v1/iam.proto
```

## Run

```bash
IAM_APP_CONFIG_PATH=app_config.toml .venv/bin/iam-service
```

## Reset database (dev)

With the server running:

```bash
# from repository root (start IAM first if needed)
make start-local          # or: python3 make/start_local.py --only iam
make reset-iam
```

``make reset-iam`` checks that ``iam.svc`` is listening on port **8803**, prints a status table with traffic lights, then calls ``ResetDatabase`` with hard-coded dev credentials (see the ``reset-iam`` target in the root ``Makefile``). The RPC wipes users/logins (and related rows), then recreates one admin user + login from the request ``username`` + ``password``.

Empty-database startup still uses ``IAM_BOOTSTRAP_*`` in ``.env.local`` for automatic admin creation when the logins table is empty.
