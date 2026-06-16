"""Unit tests for DynamoDB filter composition for account user listing."""

from __future__ import annotations

from iam_service.database.user_account_list_filters import user_account_list_filter_expression


def test_no_expression_when_include_deleted_and_no_other_filters() -> None:
    assert (
        user_account_list_filter_expression(
            include_deleted=True,
            user_type_id=None,
            enabled_equals=None,
            name_contains=None,
        )
        is None
    )


def test_soft_delete_guard_when_omitting_deleted_rows() -> None:
    expr = user_account_list_filter_expression(
        include_deleted=False,
        user_type_id=None,
        enabled_equals=None,
        name_contains=None,
    )
    assert expr is not None


def test_optional_filters_combine_with_soft_delete_guard() -> None:
    expr = user_account_list_filter_expression(
        include_deleted=False,
        user_type_id="223e4567-e89b-12d3-a456-426614174001",
        enabled_equals=True,
        name_contains="Lee",
    )
    assert expr is not None
