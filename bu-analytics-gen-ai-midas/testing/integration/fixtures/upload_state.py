"""Pydantic state model for an uploaded test dataset."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from returns.result import Failure, Result, Success

from testing.api_client.client import MidasHttpClient
from testing.api_client.http_types import MultipartFile


class UploadedDatasetState(BaseModel):
    """Holds the dataset_id returned after a successful upload."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    dataset_id: str

    @staticmethod
    def new(
        client: MidasHttpClient,
        csv_bytes: bytes,
    ) -> Result["UploadedDatasetState", Exception]:
        """Upload csv_bytes via POST /api/v1/upload; return state or Failure."""
        file = MultipartFile.new("test.csv", csv_bytes, "text/csv")
        result = client.post_multipart(
            "/api/v1/upload",
            fields={
                "target_variable": "target_flag",
                "target_variable_type": "Categorical",
            },
            files=[file],
        )
        match result:
            case Success(resp):
                return _parse_upload_response(resp)
            case Failure(exc):
                return Failure(exc)
        return Failure(RuntimeError("unreachable"))


def _parse_upload_response(
    resp: object,
) -> Result["UploadedDatasetState", Exception]:
    """Extract dataset_id from a successful upload response."""
    import httpx

    if not isinstance(resp, httpx.Response):
        return Failure(TypeError("expected httpx.Response"))
    if resp.status_code != 200:
        return Failure(RuntimeError(f"upload returned HTTP {resp.status_code}"))
    body = resp.json()
    dataset_id = body.get("dataset_id")
    if not dataset_id:
        return Failure(KeyError("dataset_id missing from upload response"))
    return Success(UploadedDatasetState(dataset_id=str(dataset_id)))
