from unittest.mock import AsyncMock, patch

from typer.testing import CliRunner

from src.cli import app

runner = CliRunner()


def services():
    return (
        patch("src.cli.init_pg", AsyncMock()),
        patch("src.cli.close_pg", AsyncMock()),
        patch("src.cli.confluence.init_client", AsyncMock()),
        patch("src.cli.confluence.close_client", AsyncMock()),
    )


def run(args, **patches):
    a, b, c, d = services()
    with a, b, c, d:
        return runner.invoke(app, args)


def test_backup_command_exit_code_reflects_errors():
    ok = {"backed_up_pages": 3, "expected_pages": 3, "errors": {}}
    with patch("src.cli.backup_space", AsyncMock(return_value=ok)):
        result = run(["backup", "DOC"])
    assert result.exit_code == 0 and "3/3 pages" in result.output
    bad = {**ok, "errors": {"1": "boom"}}
    with patch("src.cli.backup_space", AsyncMock(return_value=bad)):
        assert run(["backup", "DOC", "--no-index"]).exit_code == 1


def test_verify_command():
    with patch("src.cli.verify_space", return_value=[]):
        assert "OK" in run(["verify", "DOC"]).output
    with patch("src.cli.verify_space", return_value=["broken"]):
        result = run(["verify", "DOC"])
    assert result.exit_code == 1 and "broken" in result.output


def test_curate_command():
    with patch("src.cli.curate_space", AsyncMock(return_value={"documents": 2})):
        result = run(["curate", "DOC", "--threshold", "0.9"])
    assert result.exit_code == 0 and '"documents": 2' in result.output
