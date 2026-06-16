"""DynamoDB FilterExpression helpers for ``ListUsersByAccount``."""

from __future__ import annotations

from boto3.dynamodb.conditions import Attr

from iam_service.database.filters import active_item_filter


def user_account_list_filter_expression(
    *,
    include_deleted: bool,
    user_type_id: str | None,
    enabled_equals: bool | None,
    name_contains: str | None,
) -> Attr | None:
    """AND-combine soft-delete guard with optional user_type, enabled, and name filters."""
    parts: list[Attr] = []
    base = active_item_filter(include_deleted=include_deleted)
    if base is not None:
        parts.append(base)
    if user_type_id:
        parts.append(Attr("user_type_id").eq(user_type_id))
    if enabled_equals is not None:
        parts.append(Attr("enabled").eq(enabled_equals))
    if name_contains:
        needle = name_contains.strip()
        if needle:
            parts.append(Attr("first_name").contains(needle) | Attr("last_name").contains(needle))
    if not parts:
        return None
    combined: Attr = parts[0]
    for extra in parts[1:]:
        combined = combined & extra
    return combined
