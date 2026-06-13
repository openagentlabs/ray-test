"""Pydantic v2 models for ISG supplementary scan CSV schemas.

Three file types are supported:
  - ContainerImageRow  — container_images.csv  (14 columns)
  - OssPackageRow      — oss_packages.csv       (14 columns, identical schema)
  - IacRow             — iac.csv                (8 columns)

Schema detection: call detect_schema(headers) with the list of CSV header
strings. Returns the model class to use, or raises ValueError if no schema
matches.
"""
from __future__ import annotations

from typing import Literal, Optional, Type

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ---------------------------------------------------------------------------
# Shared severity enum
# ---------------------------------------------------------------------------

VALID_SEVERITIES = {"CRITICAL", "HIGH", "MEDIUM", "LOW", ""}


# ---------------------------------------------------------------------------
# Container image / OSS package schema  (identical columns)
# ---------------------------------------------------------------------------

_CVE_COLUMNS = {
    "Package",
    "Version",
    "Path",
    "Line(s)",
    "Git Org",
    "Git Repository",
    "Vulnerability",
    "Severity",
    "Description",
    "Licenses",
    "Fix Version",
    "Registry URL",
    "Root Package",
    "Root Version",
}


class CvePackageRow(BaseModel):
    """One finding row from container_images.csv or oss_packages.csv."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    Package: str
    Version: str
    Path: str
    Lines: str = Field(alias="Line(s)")
    Git_Org: str = Field(alias="Git Org")
    Git_Repository: str = Field(alias="Git Repository")
    Vulnerability: str
    Severity: str
    Description: str
    Licenses: str
    Fix_Version: str = Field(alias="Fix Version")
    Registry_URL: str = Field(alias="Registry URL")
    Root_Package: str = Field(alias="Root Package")
    Root_Version: str = Field(alias="Root Version")

    @field_validator("Severity")
    @classmethod
    def severity_must_be_known(cls, v: str) -> str:
        upper = v.strip().upper()
        if upper not in VALID_SEVERITIES:
            raise ValueError(
                f"Unknown Severity value '{v}'. Expected one of: CRITICAL, HIGH, MEDIUM, LOW."
            )
        return upper

    @field_validator("Package", "Vulnerability")
    @classmethod
    def must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Field must not be empty.")
        return v.strip()


# ---------------------------------------------------------------------------
# IaC schema
# ---------------------------------------------------------------------------

_IAC_COLUMNS = {
    "Resource",
    "Path",
    "Git Org",
    "Git Repository",
    "Misconfigurations",
    "Severity",
    "Policy title",
    "Guideline",
}


class IacRow(BaseModel):
    """One finding row from iac.csv.

    Rows with an empty Misconfigurations field are informational (pass rows
    exported by Checkov) and are accepted but flagged.
    """

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    Resource: str
    Path: str
    Git_Org: str = Field(alias="Git Org")
    Git_Repository: str = Field(alias="Git Repository")
    Misconfigurations: str
    Severity: str
    Policy_title: str = Field(alias="Policy title")
    Guideline: str

    @field_validator("Severity")
    @classmethod
    def severity_must_be_known(cls, v: str) -> str:
        upper = v.strip().upper()
        if upper not in VALID_SEVERITIES:
            raise ValueError(
                f"Unknown Severity value '{v}'. Expected one of: HIGH, MEDIUM, LOW or empty."
            )
        return upper

    @property
    def is_informational(self) -> bool:
        """True when Misconfigurations is empty (a Checkov pass/info row)."""
        return not self.Misconfigurations.strip()


# ---------------------------------------------------------------------------
# Schema detection
# ---------------------------------------------------------------------------

ScanRowType = Literal["container", "oss", "iac"]


def detect_schema(
    headers: list[str],
) -> tuple[ScanRowType, Type[CvePackageRow] | Type[IacRow]]:
    """Return (scan_type, ModelClass) for the given CSV header list.

    Raises ValueError if the headers do not match any known schema.
    """
    header_set = set(h.strip() for h in headers)

    if header_set == _IAC_COLUMNS:
        return "iac", IacRow

    if header_set == _CVE_COLUMNS:
        # container and oss share the same schema; caller must supply the type
        # hint via filename, but we return "container" as the default label.
        return "container", CvePackageRow

    missing_cve = _CVE_COLUMNS - header_set
    missing_iac = _IAC_COLUMNS - header_set
    extra = header_set - (_CVE_COLUMNS | _IAC_COLUMNS)

    details = []
    if missing_cve <= {"Registry URL", "Root Package", "Root Version"}:
        details.append(
            f"Looks like a CVE scan but missing columns: {sorted(missing_cve)}"
        )
    elif missing_iac <= {"Guideline"}:
        details.append(
            f"Looks like an IaC scan but missing columns: {sorted(missing_iac)}"
        )
    else:
        details.append(f"Does not match container/oss schema (missing {sorted(missing_cve)})")
        details.append(f"Does not match iac schema (missing {sorted(missing_iac)})")
    if extra:
        details.append(f"Unexpected columns: {sorted(extra)}")

    raise ValueError(
        "Unrecognised CSV schema.\n  " + "\n  ".join(details)
    )
