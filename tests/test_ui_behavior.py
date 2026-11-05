"""Run the real web/js preview/sample methods under Node's VM (no browser/network)."""
import shutil
import subprocess
from pathlib import Path


def test_preview_and_sample_refresh_health_on_success_and_failure():
    node = shutil.which("node")
    assert node, "node is required for the UI behaviour regression"
    script = Path(__file__).resolve().parent / "ui_behavior.js"
    result = subprocess.run([node, str(script)], capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "ui behaviour ok" in result.stdout
