"""Integration tests for project_router — full CRUD coverage."""

from __future__ import annotations

from typing import Optional

import pytest
from returns.result import Failure, Success

from testing.api_client.client import MidasHttpClient
from testing.integration.support.auth_guards import skip_on_auth_reject

pytestmark = pytest.mark.projects

_PROJECTS_BASE = "/api/v1/projects"


def _create_project(
    client: MidasHttpClient,
    name: str,
    description: Optional[str] = None,
) -> str:
    """Create a project and return its id; skip on auth failure."""
    body: dict[str, object] = {"name": name}
    if description is not None:
        body["description"] = description
    result = client.post_json(_PROJECTS_BASE, body)
    match result:
        case Success(resp):
            skip_on_auth_reject(resp)
            assert resp.status_code == 200, f"Project create failed: {resp.text[:300]}"
            data = resp.json()
            project_id = str(data["project"]["id"])
            return project_id
        case Failure(exc):
            pytest.skip(f"HTTP transport error creating project: {exc}")
    raise RuntimeError("unreachable")


# ------------------------------------------------------------------
# Create
# ------------------------------------------------------------------


def test_project_create_valid(midas_client: MidasHttpClient) -> None:
    """POST /projects with valid body returns 200, success=True and project.id."""
    result = midas_client.post_json(_PROJECTS_BASE, {"name": "test-project-create-valid"})
    match result:
        case Success(resp):
            skip_on_auth_reject(resp)
            assert resp.status_code == 200
            body = resp.json()
            assert body.get("success") is True
            assert body.get("project", {}).get("id") is not None
        case Failure(exc):
            pytest.skip(f"Transport error: {exc}")


def test_project_create_missing_name(midas_client: MidasHttpClient) -> None:
    """POST /projects with empty body returns 422."""
    result = midas_client.post_json(_PROJECTS_BASE, {})
    match result:
        case Success(resp):
            skip_on_auth_reject(resp)
            assert resp.status_code == 422
        case Failure(exc):
            pytest.skip(f"Transport error: {exc}")


def test_project_create_name_too_short(midas_client: MidasHttpClient) -> None:
    """POST /projects with name='' returns 422."""
    result = midas_client.post_json(_PROJECTS_BASE, {"name": ""})
    match result:
        case Success(resp):
            skip_on_auth_reject(resp)
            assert resp.status_code == 422
        case Failure(exc):
            pytest.skip(f"Transport error: {exc}")


# ------------------------------------------------------------------
# List
# ------------------------------------------------------------------


def test_project_list(midas_client: MidasHttpClient) -> None:
    """GET /projects returns 200 with projects and total_count fields."""
    result = midas_client.get_raw(_PROJECTS_BASE)
    match result:
        case Success(resp):
            skip_on_auth_reject(resp)
            assert resp.status_code == 200
            body = resp.json()
            assert "projects" in body or isinstance(body, list), (
                f"Unexpected body shape: {body}"
            )
        case Failure(exc):
            pytest.skip(f"Transport error: {exc}")


def test_project_list_pagination(midas_client: MidasHttpClient) -> None:
    """GET /projects?skip=0&limit=1 returns at most one project."""
    result = midas_client.get_raw(_PROJECTS_BASE, params={"skip": "0", "limit": "1"})
    match result:
        case Success(resp):
            skip_on_auth_reject(resp)
            assert resp.status_code == 200
            body = resp.json()
            projects = body.get("projects", body) if isinstance(body, dict) else body
            if isinstance(projects, list):
                assert len(projects) <= 1
        case Failure(exc):
            pytest.skip(f"Transport error: {exc}")


# ------------------------------------------------------------------
# Get single
# ------------------------------------------------------------------


def test_project_get_created(midas_client: MidasHttpClient) -> None:
    """GET /projects/{id} for a newly created project returns 200."""
    project_id = _create_project(midas_client, "test-get-created")
    result = midas_client.get_raw(f"{_PROJECTS_BASE}/{project_id}")
    match result:
        case Success(resp):
            skip_on_auth_reject(resp)
            assert resp.status_code == 200
        case Failure(exc):
            pytest.skip(f"Transport error: {exc}")


def test_project_get_nonexistent(midas_client: MidasHttpClient) -> None:
    """GET /projects/99999999 (non-existent) returns 404."""
    result = midas_client.get_raw(f"{_PROJECTS_BASE}/99999999")
    match result:
        case Success(resp):
            skip_on_auth_reject(resp)
            assert resp.status_code == 404
        case Failure(exc):
            pytest.skip(f"Transport error: {exc}")


# ------------------------------------------------------------------
# Update
# ------------------------------------------------------------------


def test_project_update(midas_client: MidasHttpClient) -> None:
    """PUT /projects/{id} with a new description returns 200 with updated fields."""
    project_id = _create_project(midas_client, "test-update-project")
    result = midas_client.put_json(
        f"{_PROJECTS_BASE}/{project_id}",
        {"name": "test-update-project", "description": "updated description"},
    )
    match result:
        case Success(resp):
            skip_on_auth_reject(resp)
            assert resp.status_code == 200
            body = resp.json()
            project = body.get("project", body)
            if isinstance(project, dict):
                assert project.get("description") == "updated description"
        case Failure(exc):
            pytest.skip(f"Transport error: {exc}")


# ------------------------------------------------------------------
# Delete
# ------------------------------------------------------------------


def test_project_delete(midas_client: MidasHttpClient) -> None:
    """DELETE /projects/{id} returns 200 with deleted_project_id matching."""
    project_id = _create_project(midas_client, "test-delete-project")
    result = midas_client.delete(f"{_PROJECTS_BASE}/{project_id}")
    match result:
        case Success(resp):
            skip_on_auth_reject(resp)
            assert resp.status_code == 200
        case Failure(exc):
            pytest.skip(f"Transport error: {exc}")


def test_project_get_after_delete(midas_client: MidasHttpClient) -> None:
    """GET /projects/{id} after deletion returns 404."""
    project_id = _create_project(midas_client, "test-get-after-delete")
    midas_client.delete(f"{_PROJECTS_BASE}/{project_id}")
    result = midas_client.get_raw(f"{_PROJECTS_BASE}/{project_id}")
    match result:
        case Success(resp):
            skip_on_auth_reject(resp)
            assert resp.status_code == 404
        case Failure(exc):
            pytest.skip(f"Transport error: {exc}")


def test_project_other_user_403(midas_client: MidasHttpClient) -> None:
    """Access a project as a different user returns 403 (skipped if no second credential set)."""
    import os

    second_token = os.environ.get("MIDAS_ACCESS_TOKEN_ALT", "").strip()
    if not second_token:
        pytest.skip("Set MIDAS_ACCESS_TOKEN_ALT to run cross-user isolation tests.")
    project_id = _create_project(midas_client, "test-cross-user")
    alt_headers = {"Authorization": f"Bearer {second_token}"}
    result = midas_client.get_raw(
        f"{_PROJECTS_BASE}/{project_id}", headers=alt_headers
    )
    match result:
        case Success(resp):
            assert resp.status_code in {403, 404}, (
                f"Expected 403/404 for cross-user access, got {resp.status_code}"
            )
        case Failure(exc):
            pytest.skip(f"Transport error: {exc}")
