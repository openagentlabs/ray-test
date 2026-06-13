"""Unit tests for registry list table formatting."""

from __future__ import annotations

import json
from pathlib import Path

from tf_tool.actions.registry_search.list_display import (
    compute_first_row_number,
    compute_page_number,
    format_module_list_table,
    format_registry_list_table,
)
from tf_tool.actions.registry_search.models import (
    RegistryListOutput,
    RegistryModuleSummary,
    RegistrySearchMeta,
)

_FIXTURE = Path(__file__).parent / "fixtures" / "registry_search_vpc.json"


def _modules_from_fixture() -> list[RegistryModuleSummary]:
    payload = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    modules = [RegistryModuleSummary.model_validate(item) for item in payload["modules"]]
    if len(modules) == 1:
        modules.append(
            modules[0].model_copy(
                update={
                    "id": "terraform-aws-modules/ec2-instance/aws/6.4.0",
                    "name": "ec2-instance",
                    "version": "6.4.0",
                    "description": "Terraform module to create AWS EC2 instance(s) resources",
                },
            ),
        )
    return modules


def test_format_module_list_table_numbers_rows_continuously_from_offset() -> None:
    modules = _modules_from_fixture()
    table = format_module_list_table(modules, start_index=21)

    assert "21." in table
    assert "22." in table
    assert " 1." not in table
    assert modules[0].source_address in table


def test_format_module_list_table_numbers_rows() -> None:
    modules = _modules_from_fixture()
    table = format_module_list_table(modules)

    assert "1." in table
    assert "2." in table
    assert modules[0].source_address in table
    assert modules[0].version in table
    assert "Name" in table
    assert "Version" in table
    assert "Description" in table


def test_format_registry_list_table_uses_offset_for_row_numbers() -> None:
    modules = _modules_from_fixture()
    output = RegistryListOutput(
        provider="aws",
        namespace=None,
        verified=None,
        limit=2,
        offset=20,
        meta=RegistrySearchMeta(limit=2, current_offset=20, next_offset=22, prev_offset=18),
        modules=modules,
        count=2,
    )

    rendered = format_registry_list_table(output)

    assert "page 11" in rendered
    assert "21." in rendered
    assert "22." in rendered


def test_format_registry_list_table_includes_summary() -> None:
    modules = _modules_from_fixture()
    output = RegistryListOutput(
        provider="aws",
        namespace=None,
        verified=None,
        limit=2,
        offset=0,
        meta=RegistrySearchMeta(limit=2, current_offset=0, next_offset=2),
        modules=modules,
        count=2,
    )

    rendered = format_registry_list_table(output)

    assert "Terraform Registry modules" in rendered
    assert "provider=aws" in rendered
    assert "page 1" in rendered
    assert "2 per page" in rendered
    assert "1." in rendered


def test_compute_first_row_number_from_offset() -> None:
    assert compute_first_row_number(offset=0) == 1
    assert compute_first_row_number(offset=20) == 21


def test_compute_page_number_from_offset() -> None:
    assert compute_page_number(offset=0, limit=20) == 1
    assert compute_page_number(offset=20, limit=20) == 2
    assert compute_page_number(offset=40, limit=15) == 3
