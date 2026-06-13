"""Pydantic record models (Postgres row shapes) for solutions.svc."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from solutions_service.database.models.records import SolutionDocumentRecord


def test_solution_document_record_soft_delete_fields() -> None:
    rec = SolutionDocumentRecord(
        id="423e4567-e89b-12d3-a456-426614174000",
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-02T00:00:00Z",
        deleted_at="2026-01-03T00:00:00Z",
        is_deleted=True,
        solution_id="423e4567-e89b-12d3-a456-426614174001",
        name="spec.pdf",
        description="BRD",
        path="/files/spec.pdf",
    )
    assert rec.is_deleted is True
    assert rec.deleted_at.endswith("Z")


def test_solution_document_record_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        SolutionDocumentRecord.model_validate(
            {
                "id": "doc-1",
                "created_at": "t",
                "updated_at": "t",
                "solution_id": "sol-1",
                "name": "n",
                "path": "/p",
                "extra": True,
            },
        )
