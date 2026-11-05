import pytest


@pytest.fixture(autouse=True)
def _reset_runtime_fallback():
    """Runtime CPU fallback is process-global state; never let it leak between tests."""
    from backend import device_fallback as df
    df.reset_runtime_fallback()
    yield
    df.reset_runtime_fallback()


@pytest.fixture(autouse=True)
def _isolated_log_dir(tmp_path, monkeypatch):
    """Launch/server logs never touch the real per-user log folder during tests."""
    monkeypatch.setenv("T2A_LOG_DIR", str(tmp_path / "t2a-logs"))
