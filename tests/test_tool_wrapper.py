import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_tool_wrapper import ToolCallError, call_tool


def test_retry_exhausts_and_raises():
    try:
        call_tool("search_web", {"force_fail": True})
    except ToolCallError as e:
        assert "retries exhausted" in str(e)
        return
    raise AssertionError("expected ToolCallError after retries")


def test_missing_query_raises_without_masking():
    """Missing query is a validation error, not a transient one.

    Currently FAILS on purpose: the retry decorator re-feeds the error,
    call_tool then raises 'Hallucinated param detected' on retry, and
    the final 'retries exhausted' error no longer mentions 'query'.
    The original error is masked. After the fix this should raise
    immediately (or at least preserve 'query' in the final error).
    """
    try:
        call_tool("search_web", {})
    except ToolCallError as e:
        assert "query" in str(e), f"original error masked: {e}"
        return
    raise AssertionError("expected ToolCallError for missing query")


def test_no_hallucinated_param_on_retry():
    """Regression test for the bug: retry must not inject hallucinated params.

    Call with params as a keyword argument, so the decorator's kwargs
    actually contains 'params' — the path the original script pollutes.
    Currently FAILS on purpose: the decorator writes
    hallucinated_key into the caller's params dict on retry.
    That failing test is what triggers the Devin auto-fix workflow in CI.
    """
    params = {"force_fail": True}
    original = dict(params)
    try:
        call_tool(tool_name="search_web", params=params)
    except ToolCallError:
        pass
    assert params == original, f"params polluted on retry: {params}"
    assert "hallucinated_key" not in params
