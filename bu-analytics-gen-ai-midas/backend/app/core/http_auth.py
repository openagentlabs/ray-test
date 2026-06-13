"""Shared helpers for extracting bearer tokens from requests (header or query)."""

from starlette.requests import Request


def extract_bearer_token(request: Request) -> str:
    auth_header = request.headers.get("authorization", "")
    if auth_header:
        prefix = "bearer "
        if auth_header.lower().startswith(prefix):
            return auth_header[len(prefix) :].strip()
    query_token = request.query_params.get("token")
    if query_token:
        return query_token.strip()
    return ""
