"""
Regression tests for FastAPI ``BackgroundTasks`` declarations.

Background
----------
``POST /api/v1/train-multiple-models`` (and similar endpoints) is supposed to
return immediately with a ``job_id`` and run the actual training as a FastAPI
``BackgroundTask``. For weeks it 504-ed in production while auto-training and
segment-training (which use the same ``BackgroundTasks`` plumbing) worked.

Root cause: the background worker was declared ``async def`` but its body is
entirely synchronous, CPU-bound work (``manual_config_service.
train_multiple_models`` does pandas / sklearn fits, CV folds, hyperparameter
search). FastAPI runs ``async def`` background tasks **on the same event loop
that serves requests**, so a CPU-bound coroutine that never yields pins the
loop for the entire training duration. Status polls, new training requests,
ALB / ingress health checks, and Kubernetes liveness probes all wait in queue
and time out at the idle limit -> 504 Gateway Time-out / pod restart -> the
"Job was interrupted by server restart. Please retry." pattern the UI saw on
auto-analysis.

Fix: declare each such function ``def`` (not ``async def``). FastAPI's
``BackgroundTasks`` runs sync functions through ``anyio``'s thread limiter,
keeping the event loop free.

The same anti-pattern was found and fixed on three more workers that the auto-
analysis flow exercises end-to-end on every dataset upload:

  - ``_run_classify_vars_background``           (variable classification)
  - ``_run_dataset_type_classification_bg``     (ML problem type)
  - ``_run_global_model_background``            (global model training)

These tests lock in the correct declaration so the regression cannot quietly
come back via a refactor that "just makes it consistent" with the route
handlers (which IS ``async def``, correctly), and add an AST-based audit so
**any future** ``background_tasks.add_task(...)`` call site is checked at CI
time, not in production at 3am.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from typing import Iterable, Set, Tuple

import pytest


# ---------------------------------------------------------------------------
# Per-function locks (the worst offenders we've already paid the on-call tax
# for; keeping explicit asserts so the failure message names the exact route).
# ---------------------------------------------------------------------------


def test_train_multiple_models_background_is_sync_def_not_async_def():
    """The function must be plain ``def``, not ``async def``.

    ``inspect.iscoroutinefunction`` is the canonical way to detect ``async
    def``. If a future refactor turns this back into a coroutine -- which is
    the exact regression that produced the multi-month 504 outage on
    /train-multiple-models -- this assertion fails immediately and CI rejects
    the change.
    """
    from app.api.routes import train_multiple_models_background

    assert not inspect.iscoroutinefunction(train_multiple_models_background), (
        "train_multiple_models_background must NOT be async def. The body "
        "is CPU-bound (pandas / sklearn fit, CV folds, hyperparameter "
        "search) and an async coroutine pins the event loop until "
        "training finishes -- the exact failure pattern the UI saw from "
        "trainMultipleModels while auto-training (already def) worked. "
        "Declared def, FastAPI BackgroundTasks runs it on anyio's thread "
        "limiter so the event loop stays free."
    )

    assert inspect.isfunction(train_multiple_models_background), (
        "train_multiple_models_background must be a regular function so "
        "FastAPI BackgroundTasks dispatches it to the anyio thread pool"
    )


def test_other_training_background_tasks_are_sync_too():
    """All long-running training background tasks must be sync ``def`` for
    the same reason. A sibling regression in any of these would reproduce
    the same 504 / pod-restart pattern, just on a different endpoint."""
    from app.api.routes import (
        run_auto_training_background,
        run_segment_auto_training_background,
        run_segment_training_background,
    )

    for fn in (
        run_auto_training_background,
        run_segment_auto_training_background,
        run_segment_training_background,
    ):
        assert not inspect.iscoroutinefunction(fn), (
            f"{fn.__name__} must be sync def -- async def + sync CPU body "
            "pins the event loop and 504s every other request on the "
            "worker for the duration of the training run"
        )


def test_auto_analysis_background_tasks_are_sync_def():
    """Auto-analysis runs three background workers per dataset upload:
    variable classification, ML problem-type classification, and global
    model training. All three previously shipped as ``async def`` with
    fully synchronous bodies (sync LLM HTTP calls + sync pandas / sklearn
    work) -- pinning the event loop for the full LLM round-trip / training
    run, which is exactly how the UI ended up seeing both
    ``/dataset-type-classification/status/{job_id}`` 404s and
    ``"Job was interrupted by server restart. Please retry."`` after long
    auto-analysis runs (Kubernetes liveness probe failures restarted the
    pod, dropping in-memory job state).
    """
    from app.api.routes import (
        _run_classify_vars_background,
        _run_dataset_type_classification_bg,
        _run_global_model_background,
    )

    for fn in (
        _run_classify_vars_background,
        _run_dataset_type_classification_bg,
        _run_global_model_background,
    ):
        assert not inspect.iscoroutinefunction(fn), (
            f"{fn.__name__} must be sync def -- it is registered as a "
            "FastAPI BackgroundTask whose body is CPU/IO-bound and "
            "synchronous; declared async def the worker pins the event "
            "loop and produces 504s + pod restarts on the auto-analysis "
            "endpoints (the exact failure the UI reported as "
            "'Dataset not found' + 'Job was interrupted by server "
            "restart' after upload)"
        )


def test_train_multiple_models_route_is_async_def():
    """Sanity: the *route handler* (the thing FastAPI invokes when the HTTP
    request hits) MUST stay ``async def``. The handler is the part that
    runs on the event loop and only does fast work (validate, register a
    job dict, schedule the background task, return). Switching it to sync
    would force FastAPI to run it in the thread pool too, which is fine
    but is NOT the fix for the 504 -- the actual 504 fix is in the
    background task. Lock in the correct shape on both sides."""
    from app.api.routes import train_multiple_models

    assert inspect.iscoroutinefunction(train_multiple_models), (
        "train_multiple_models route handler should remain async def -- it "
        "only does fast registration work and benefits from running on the "
        "event loop"
    )


# ---------------------------------------------------------------------------
# AST audit: walk routes.py for every background_tasks.add_task(...) call,
# resolve each callable, and assert none of them are async def. This is the
# guard that catches *new* offenders the moment they are added.
# ---------------------------------------------------------------------------


# Callables that intentionally use ``async def`` because they correctly
# bridge to a thread pool internally (``loop.run_in_executor(...)``) and
# thus do NOT pin the event loop. Add to this list only with a comment
# explaining why -- i.e. you have read the function body and verified it
# does not do any blocking sync work directly.
_ALLOWED_ASYNC_BACKGROUND_TASKS: Set[str] = {
    # llm_service.generate_async_knowledge_graph offloads via
    # ``loop.run_in_executor(None, self.get_knowledge_graph, ...)`` -- the
    # async wrapper only awaits an executor future, so the event loop is
    # not pinned. See backend/app/services/llm_service.py.
    "generate_async_knowledge_graph",
}


def _routes_source_path() -> Path:
    from app.api import routes

    src = inspect.getsourcefile(routes)
    assert src is not None, "could not locate source file for app.api.routes"
    return Path(src)


def _iter_background_task_callables(tree: ast.AST) -> Iterable[Tuple[str, int]]:
    """Yield (callable_name, line_number) for every
    ``background_tasks.add_task(callable, ...)`` call found in the AST.

    Both bare names (``add_task(my_fn, ...)``) and attribute accesses
    (``add_task(svc.method, ...)``) are emitted -- we only need the trailing
    identifier to look up the function on the imported module.
    """
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute) or func.attr != "add_task":
            continue
        # Confirm the receiver is the FastAPI BackgroundTasks param. The
        # parameter is named ``background_tasks`` everywhere in this file.
        receiver = func.value
        if not isinstance(receiver, ast.Name) or receiver.id != "background_tasks":
            continue
        if not node.args:
            continue
        first = node.args[0]
        if isinstance(first, ast.Name):
            yield first.id, node.lineno
        elif isinstance(first, ast.Attribute):
            yield first.attr, node.lineno


def test_all_background_tasks_in_routes_are_sync_def():
    """AST-walks routes.py for every ``background_tasks.add_task(callable,
    ...)`` and asserts the callable is **not** an ``async def`` function
    (unless explicitly allow-listed for a documented reason).

    Why an audit and not just a per-function check: the original outage
    (manual training 504) shipped through code review because reviewers
    didn't notice ``async def`` was wrong for that particular body. The
    same bug then independently shipped on three other auto-analysis
    workers. A blanket guard at the call-site level prevents the next
    "yet another sync-bodied async def" from sneaking in -- the guard
    fails the moment the new ``add_task(...)`` line is added, before the
    code can reach a deployed environment.
    """
    from app.api import routes
    from app.services import llm_service as llm_module

    src = _routes_source_path().read_text(encoding="utf-8")
    tree = ast.parse(src, filename=str(_routes_source_path()))

    seen: Set[str] = set()
    offenders: list[str] = []
    not_resolved: list[Tuple[str, int]] = []

    for name, lineno in _iter_background_task_callables(tree):
        if name in seen:
            continue
        seen.add(name)

        if name in _ALLOWED_ASYNC_BACKGROUND_TASKS:
            # Allow-listed; we have read the body and confirmed it offloads
            # to a thread pool internally. Skip.
            continue

        # Resolve the callable. Look in routes.py first (most are local),
        # then in known imported modules (currently just llm_service).
        fn = getattr(routes, name, None)
        if fn is None:
            fn = getattr(llm_module, name, None)
        if fn is None:
            for attr_name in dir(routes):
                attr = getattr(routes, attr_name)
                if inspect.ismodule(attr):
                    candidate = getattr(attr, name, None)
                    if candidate is not None and (
                        inspect.isfunction(candidate)
                        or inspect.ismethod(candidate)
                        or inspect.iscoroutinefunction(candidate)
                    ):
                        fn = candidate
                        break

        if fn is None:
            not_resolved.append((name, lineno))
            continue

        if inspect.iscoroutinefunction(fn):
            offenders.append(
                f"  - {name} (registered at routes.py:{lineno}) is "
                f"async def. FastAPI BackgroundTasks runs async def "
                f"workers on the request-serving event loop. If the body "
                f"is synchronous CPU/IO work the event loop is pinned for "
                f"the full duration -> 504s on every other request and "
                f"pod restarts on K8s liveness probe failure. Convert to "
                f"plain def, or -- if the body is genuinely awaitable -- "
                f"add the name to _ALLOWED_ASYNC_BACKGROUND_TASKS with a "
                f"comment explaining why."
            )

    assert not offenders, (
        "async def callables registered via background_tasks.add_task in "
        "routes.py:\n" + "\n".join(offenders)
    )

    # Soft check: it is fine if some referenced names cannot be resolved
    # (e.g. a third-party module not installed in the test env). We don't
    # fail the test on that -- the audit's purpose is to catch async-def
    # regressions, not to enforce import hygiene. Print so test runners
    # invoked with -s surface the unresolved names if someone is debugging
    # the audit.
    if not_resolved:
        print(
            "[audit] background_tasks.add_task callables that could not "
            "be resolved against app.api.routes / app.services."
            "llm_service:"
        )
        for name, lineno in not_resolved:
            print(f"  - {name} (routes.py:{lineno})")
