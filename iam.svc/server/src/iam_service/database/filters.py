"""Reusable DynamoDB condition helpers."""

from __future__ import annotations

from boto3.dynamodb.conditions import Attr


def active_item_filter(*, include_deleted: bool) -> Attr | None:
    """Return a filter for soft-deleted items; ``None`` means no filter."""
    if include_deleted:
        return None
    return Attr("is_deleted").not_exists() | Attr("is_deleted").eq(False)
