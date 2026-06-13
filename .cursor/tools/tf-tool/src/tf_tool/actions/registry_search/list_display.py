"""Human-readable table formatting for registry list results."""

from __future__ import annotations

from tf_tool.actions.registry_search.models import RegistryListOutput, RegistryModuleSummary

_NAME_WIDTH = 42
_VERSION_WIDTH = 12
_DESCRIPTION_WIDTH = 48


def _truncate(text: str, width: int) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= width:
        return collapsed
    if width <= 3:
        return collapsed[:width]
    return f"{collapsed[: width - 3]}..."


def format_module_list_table(
    modules: list[RegistryModuleSummary],
    *,
    start_index: int = 1,
) -> str:
    """Format modules as a numbered table starting at ``start_index``."""
    if not modules:
        return "No Terraform modules matched the list filters."

    last_index = start_index + len(modules) - 1
    number_width = max(3, len(str(last_index)))
    header = (
        f"{'#':>{number_width}}  {'Name':<{_NAME_WIDTH}} {'Version':<{_VERSION_WIDTH}} Description"
    )
    divider = "-" * len(header)
    rows = [
        _format_module_row(index, module, number_width=number_width)
        for index, module in enumerate(modules, start=start_index)
    ]
    return "\n".join([header, divider, *rows])


def _format_module_row(
    index: int,
    module: RegistryModuleSummary,
    *,
    number_width: int = 3,
) -> str:
    name = _truncate(module.source_address, _NAME_WIDTH)
    version = _truncate(module.version, _VERSION_WIDTH)
    description = _truncate(module.description or "(no description)", _DESCRIPTION_WIDTH)
    return (
        f"{index:{number_width}}. {name:<{_NAME_WIDTH}} {version:<{_VERSION_WIDTH}} {description}"
    )


def compute_page_number(*, offset: int, limit: int) -> int:
    """Return the 1-based page number for a given offset and page size."""
    if limit < 1:
        return 1
    return offset // limit + 1


def compute_first_row_number(*, offset: int) -> int:
    """Return the 1-based row number for the first item on a page."""
    return offset + 1


def format_registry_list_summary(output: RegistryListOutput) -> str:
    """Build a short heading for a list result."""
    filters: list[str] = []
    if output.provider is not None:
        filters.append(f"provider={output.provider}")
    if output.namespace is not None:
        filters.append(f"namespace={output.namespace}")
    if output.verified is True:
        filters.append("verified only")
    filter_text = f" ({', '.join(filters)})" if filters else ""
    page = compute_page_number(offset=output.offset, limit=output.limit)
    return (
        f"Terraform Registry modules{filter_text} — "
        f"page {page}, {output.limit} per page, showing {output.count}:"
    )


def format_registry_list_table(output: RegistryListOutput) -> str:
    """Format a full list response for interactive CLI output."""
    summary = format_registry_list_summary(output)
    start_index = compute_first_row_number(offset=output.offset)
    table = format_module_list_table(output.modules, start_index=start_index)
    return f"{summary}\n\n{table}"
