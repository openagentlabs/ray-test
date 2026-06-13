"""
Tests for the alias-not-copy optimization in
``DataFrameStateManager.update_dataframe``.

The previous implementation always called ``df.copy()`` when seeding
``_full_dataframes[dataset_id]`` on the first ``update_dataframe`` invocation
for a dataset. On the ``/upload`` hot path with a 2.5 GB CSV that copy alone
cost ~10-30 s on the request budget and was a meaningful contributor to the
504 Gateway Timeout the user kept seeing on Submit.

The new implementation aliases the caller's frame instead. The single owner
of the master frame becomes ``_full_dataframes[dataset_id]`` once the route's
local ``df`` falls out of scope. Subsequent ``update_dataframe`` calls (post
exclusion or variable-removal) still copy via the existing
``first_entire_upload`` branch, so transformations never mutate the master.

These tests lock the behavior in:

* Aliasing on first-time entire-scope upload (no copy).
* Re-storing transformed frames on subsequent calls still copies the
  transformed input, so the master stays untouched by transformations.
"""

from __future__ import annotations

import pandas as pd
import pytest


@pytest.fixture
def fresh_state_manager():
    from app.services.dataframe_state_manager import dataframe_state_manager

    dataframe_state_manager._full_dataframes.clear()
    dataframe_state_manager._processed_dataframes.clear()
    dataframe_state_manager._transformed_copies.clear()
    dataframe_state_manager._dataset_metadata.clear()
    dataframe_state_manager._version_counters.clear()
    if hasattr(dataframe_state_manager, "_active_scope"):
        dataframe_state_manager._active_scope.clear()
    if hasattr(dataframe_state_manager, "_split_indices"):
        dataframe_state_manager._split_indices.clear()
    yield dataframe_state_manager
    dataframe_state_manager._full_dataframes.clear()
    dataframe_state_manager._processed_dataframes.clear()
    dataframe_state_manager._transformed_copies.clear()
    dataframe_state_manager._dataset_metadata.clear()
    dataframe_state_manager._version_counters.clear()


def test_first_entire_upload_aliases_caller_frame_no_copy(fresh_state_manager):
    """First-time entire-scope ``update_dataframe`` must alias the caller's
    frame into ``_full_dataframes`` (no ``df.copy()``).

    Object identity is the gold standard here: ``id(stored) == id(input)``
    confirms there's been no allocation of a fresh DataFrame. If a copy
    sneaks back in (for example via a refactor that defaults to ``df.copy()``)
    this test fails immediately.
    """
    state = fresh_state_manager
    df = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
    dataset_id = "alias-test-1"

    state.update_dataframe(dataset_id, df, original_shape=df.shape)

    stored = state._full_dataframes[dataset_id]
    assert stored is df, (
        "first-time entire upload must alias the caller's frame; got a copy "
        "(id mismatch). This regression was a 10-30s cost on /upload of a "
        "2.5GB CSV."
    )
    # The "entire" scope copy should also alias the same object (existing
    # behavior, preserved by my change).
    assert state._transformed_copies[dataset_id]["entire"] is df
    assert state._processed_dataframes[dataset_id] is df


def test_first_upload_uses_processed_when_input_is_empty(fresh_state_manager):
    """If the caller passes an empty df but a non-empty processed frame is
    already cached, the master is aliased to the processed frame -- never to
    the empty caller. This guards split scopes from poisoning the master."""
    state = fresh_state_manager
    dataset_id = "alias-test-empty"
    pre = pd.DataFrame({"a": [1, 2, 3]})
    state._processed_dataframes[dataset_id] = pre

    empty_df = pd.DataFrame({"a": []})
    state.update_dataframe(dataset_id, empty_df, original_shape=(0, 1))

    stored = state._full_dataframes[dataset_id]
    assert stored is pre, "empty input must not become the master"


def test_second_update_does_not_overwrite_master(fresh_state_manager):
    """Subsequent ``update_dataframe`` calls (e.g. after exclusion rules /
    variable-removal) must NOT touch ``_full_dataframes`` -- the master stays
    pinned to the original first-upload frame, while ``_processed_dataframes``
    and the per-scope ``_transformed_copies`` see the new transformed frame.

    With my alias change a second call could in principle observe the master
    if mutation happened on the input. This test confirms the original
    pristine frame survives a second update with a different shape.
    """
    state = fresh_state_manager
    dataset_id = "alias-test-2"

    original = pd.DataFrame({"a": [1, 2, 3, 4, 5], "b": [10, 20, 30, 40, 50]})
    state.update_dataframe(dataset_id, original, original_shape=original.shape)

    transformed = original.iloc[:3].copy()
    transformed["c"] = [100, 200, 300]
    state.update_dataframe(
        dataset_id, transformed, original_shape=original.shape
    )

    master = state._full_dataframes[dataset_id]
    assert master is original, (
        "second update must not replace the master frame"
    )
    assert master.shape == (5, 2), (
        "master frame columns/rows must be untouched by the second update; "
        "got shape %s" % (master.shape,)
    )
    assert list(master.columns) == ["a", "b"]


def test_second_update_copies_transformed_input(fresh_state_manager):
    """The branch that handles non-first-time updates still does ``df.copy()``
    when storing the transformed frame -- so further mutations of the
    caller's local ``df`` post-update_dataframe don't leak into the cached
    transformed copy. Lock that in too."""
    state = fresh_state_manager
    dataset_id = "alias-test-3"

    original = pd.DataFrame({"a": [1, 2, 3]})
    state.update_dataframe(dataset_id, original, original_shape=original.shape)

    transformed = pd.DataFrame({"a": [10, 20, 30], "b": ["x", "y", "z"]})
    state.update_dataframe(
        dataset_id, transformed, original_shape=transformed.shape
    )

    cached = state._processed_dataframes[dataset_id]
    transformed.loc[0, "a"] = 999
    assert cached.loc[0, "a"] != 999, (
        "subsequent update_dataframe calls must copy the transformed input "
        "so post-update mutations don't leak into the cached frame"
    )


def test_version_counter_bumps_on_every_update(fresh_state_manager):
    """Versioning is the analytics-cache invalidation key; my aliasing
    optimization must not break it. Every ``update_dataframe`` call still
    bumps the per-dataset version counter."""
    state = fresh_state_manager
    dataset_id = "alias-test-version"

    df = pd.DataFrame({"a": [1, 2, 3]})
    state.update_dataframe(dataset_id, df, original_shape=df.shape)
    v1 = state.get_version(dataset_id)

    df2 = pd.DataFrame({"a": [1, 2, 3, 4]})
    state.update_dataframe(dataset_id, df2, original_shape=df2.shape)
    v2 = state.get_version(dataset_id)

    assert v1 == 1
    assert v2 == 2
