"""Shared CLI flow for registry list commands."""

from __future__ import annotations

import sys
from pathlib import Path

from returns.result import Failure

from tf_tool.actions.registry_search.client import RegistryClient
from tf_tool.actions.registry_search.download import download_registry_module
from tf_tool.actions.registry_search.list import fetch_registry_list, list_registry_modules_json
from tf_tool.actions.registry_search.list_display import (
    compute_first_row_number,
    compute_page_number,
    format_registry_list_table,
)
from tf_tool.actions.registry_search.list_prompt import (
    ListPromptAction,
    read_list_prompt,
)
from tf_tool.actions.registry_search.models import RegistryListOutput
from tf_tool.actions.registry_search.validation import ListRequest
from tf_tool.core.cli_output import die_json_error, emit_action
from tf_tool.core.command_label import argv_command_label
from tf_tool.core.operation_ui import get_session, run_if_session


def _fetch_list_output(
    request: ListRequest,
    *,
    client: RegistryClient | None,
    use_session: bool,
) -> RegistryListOutput:
    def _fetch() -> RegistryListOutput:
        fetched = fetch_registry_list(
            provider=request.provider,
            namespace=request.namespace,
            verified=request.verified,
            limit=request.limit,
            offset=request.offset,
            client=client,
        )
        if isinstance(fetched, Failure):
            die_json_error(fetched.failure())
        return fetched.unwrap()

    if use_session:
        return run_if_session(
            "Listing Terraform Registry modules",
            argv_command_label(default="tf-tool registry-list"),
            _fetch,
        )
    return _fetch()


def _print_list_table(output: RegistryListOutput) -> None:
    table = format_registry_list_table(output)
    session = get_session()
    if session is not None:
        session.replay_success(table)
    print(table)


def _download_selected_module(
    output: RegistryListOutput,
    global_row: int,
    *,
    destination_dir: Path | None,
    client: RegistryClient | None,
) -> None:
    module_index = global_row - output.offset - 1
    module = output.modules[module_index]
    print(
        f"\nDownloading {module.source_address} v{module.version} ...",
        flush=True,
    )
    downloaded = download_registry_module(
        module,
        destination_dir=destination_dir,
        client=client,
    )
    if isinstance(downloaded, Failure):
        die_json_error(downloaded.failure())
        return

    print(f"Downloaded to {downloaded.unwrap()}")


def _apply_page_navigation(
    prompt_action: ListPromptAction,
    *,
    offset: int,
    limit: int,
    next_offset: int | None,
    prev_offset: int | None,
) -> int | None:
    """Return the new offset after a page navigation, or ``None`` when unchanged."""
    if prompt_action == ListPromptAction.NEXT_PAGE:
        if next_offset is None:
            print("Already on the last page.", file=sys.stderr)
            return None
        return next_offset
    if prompt_action == ListPromptAction.PREV_PAGE:
        if prev_offset is not None:
            return prev_offset
        if offset <= 0:
            print("Already on the first page.", file=sys.stderr)
            return None
        return max(0, offset - limit)
    return None


def _run_interactive_list(
    request: ListRequest,
    *,
    destination_dir: Path | None = None,
    client: RegistryClient | None = None,
) -> None:
    """Browse paginated list results with row download and arrow-key paging."""
    offset = request.offset
    first_fetch = True

    while True:
        page_request = request.model_copy(update={"offset": offset})
        output = _fetch_list_output(page_request, client=client, use_session=first_fetch)
        first_fetch = False

        if not output.modules:
            if offset > 0:
                print("No modules on this page.", file=sys.stderr)
                offset = max(0, offset - request.limit)
                continue
            _print_list_table(output)
            return

        _print_list_table(output)
        page = compute_page_number(offset=output.offset, limit=output.limit)
        first_row = compute_first_row_number(offset=output.offset)
        last_row = first_row + len(output.modules) - 1
        prompt = read_list_prompt(first_row=first_row, last_row=last_row, page=page)

        if prompt.action == ListPromptAction.EXIT:
            return
        if prompt.action == ListPromptAction.SELECT and prompt.row is not None:
            _download_selected_module(
                output,
                prompt.row,
                destination_dir=destination_dir,
                client=client,
            )
            return

        new_offset = _apply_page_navigation(
            prompt.action,
            offset=offset,
            limit=request.limit,
            next_offset=output.meta.next_offset,
            prev_offset=output.meta.prev_offset,
        )
        if new_offset is not None:
            offset = new_offset


def run_list_command(
    request: ListRequest,
    *,
    json_output: bool = False,
    interactive: bool = True,
    destination_dir: Path | None = None,
    client: RegistryClient | None = None,
) -> None:
    """Fetch modules, print a table or JSON, then optionally prompt to download."""
    if json_output:
        emit_action(
            lambda: list_registry_modules_json(
                provider=request.provider,
                namespace=request.namespace,
                verified=request.verified,
                limit=request.limit,
                offset=request.offset,
                client=client,
            ),
            operation="Listing Terraform Registry modules",
            command=argv_command_label(default="tf-tool registry-list"),
        )
        return

    if interactive and sys.stdin.isatty():
        _run_interactive_list(
            request,
            destination_dir=destination_dir,
            client=client,
        )
        return

    output = _fetch_list_output(request, client=client, use_session=True)
    _print_list_table(output)
