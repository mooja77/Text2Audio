import pytest


@pytest.fixture(autouse=True)
def _reset_runtime_fallback():
    """Runtime CPU fallback is process-global state; never let it leak between tests."""
    from backend import device_fallback as df
    df.reset_runtime_fallback()
    yield
    df.reset_runtime_fallback()
