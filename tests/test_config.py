import subprocess
import sys
from pathlib import Path


def _load_settings(env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    code = "from src.config import settings; print(settings.CONFLUENCE_URL, settings.APP_API_KEY)"
    return subprocess.run(
        [sys.executable, "-c", code],
        env={"PATH": "/usr/bin:/bin", **env},
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).resolve().parents[1]),
    )


def test_settings_read_credentials_from_environment():
    result = _load_settings(
        {
            "CONFLUENCE_URL": "https://real.example/wiki",
            "CONFLUENCE_USERNAME": "u",
            "CONFLUENCE_API_TOKEN": "t",
            "APP_API_KEY": "real-key",
        }
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.split() == ["https://real.example/wiki", "real-key"]


def test_settings_fail_fast_without_required_variables():
    result = _load_settings({})
    assert result.returncode != 0
    assert "APP_API_KEY" in result.stderr
