import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_foundation_cli_check_executes():
    result = subprocess.run(
        [sys.executable, "-m", "sentinel", "check"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Stallion Sentinel" in result.stdout
    assert "Overall Status: HEALTHY" in result.stdout
    assert (PROJECT_ROOT / ".runtime" / "runs").exists()
