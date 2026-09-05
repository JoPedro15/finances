"""Unit tests for src/cli/report.py."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from src.cli.report import app

_PATCH_GEN = "src.infra.report_generator.PortfolioReportGenerator"

runner = CliRunner()


# ==============================================================================
# Helpers / fixtures
# ==============================================================================


def _mock_generator(html_path: Path) -> MagicMock:
    gen = MagicMock()
    gen.generate.return_value = html_path
    return gen


# ==============================================================================
# generate command
# ==============================================================================


def test_generate_succeeds_and_prints_path(tmp_path: Path) -> None:
    """Successful run prints the HTML path and exits 0."""
    html_path = tmp_path / "portfolio_report.html"
    html_path.touch()
    with patch(_PATCH_GEN, return_value=_mock_generator(html_path)):
        result = runner.invoke(app, ["generate", "--no-browser"])

    assert result.exit_code == 0
    assert "portfolio_report" in result.output


def test_generate_output_contains_success_label(tmp_path: Path) -> None:
    """Success message is printed on a successful run."""
    html_path = tmp_path / "portfolio_report.html"
    html_path.touch()
    with patch(_PATCH_GEN, return_value=_mock_generator(html_path)):
        result = runner.invoke(app, ["generate", "--no-browser"])

    assert "Report generated successfully" in result.output


def test_generate_passes_no_browser_flag(tmp_path: Path) -> None:
    """--no-browser flag results in open_browser=False passed to generate()."""
    html_path = tmp_path / "portfolio_report.html"
    html_path.touch()
    mock_gen = _mock_generator(html_path)
    with patch(_PATCH_GEN, return_value=mock_gen):
        runner.invoke(app, ["generate", "--no-browser"])

    mock_gen.generate.assert_called_once_with(open_browser=False)


def test_generate_opens_browser_by_default(tmp_path: Path) -> None:
    """Browser is opened by default (open_browser=True)."""
    html_path = tmp_path / "portfolio_report.html"
    html_path.touch()
    mock_gen = _mock_generator(html_path)
    with patch(_PATCH_GEN, return_value=mock_gen):
        runner.invoke(app, ["generate"])

    mock_gen.generate.assert_called_once_with(open_browser=True)


def test_generate_exits_1_on_exception(tmp_path: Path) -> None:
    """Exit code 1 and error message printed when generator raises."""
    mock_gen = MagicMock()
    mock_gen.generate.side_effect = RuntimeError("something went wrong")
    with patch(_PATCH_GEN, return_value=mock_gen):
        result = runner.invoke(app, ["generate", "--no-browser"])

    assert result.exit_code == 1
    assert "Error" in result.output
    assert "something went wrong" in result.output


def test_generate_passes_custom_output_dir(tmp_path: Path) -> None:
    """--output-dir option is forwarded to PortfolioReportGenerator."""
    html_path = tmp_path / "custom" / "portfolio_report.html"
    html_path.parent.mkdir(parents=True)
    html_path.touch()
    mock_gen = _mock_generator(html_path)
    with patch(_PATCH_GEN, return_value=mock_gen) as mock_cls:
        runner.invoke(
            app, ["generate", "--no-browser", "--output-dir", str(tmp_path / "custom")]
        )

    call_kwargs = mock_cls.call_args[1]
    assert call_kwargs["output_dir"] == tmp_path / "custom"


def test_generate_passes_custom_db_path(tmp_path: Path) -> None:
    """--db-path option is forwarded to PortfolioReportGenerator."""
    html_path = tmp_path / "portfolio_report.html"
    html_path.touch()
    db = tmp_path / "custom.db"
    mock_gen = _mock_generator(html_path)
    with patch(_PATCH_GEN, return_value=mock_gen) as mock_cls:
        runner.invoke(app, ["generate", "--no-browser", "--db-path", str(db)])

    call_kwargs = mock_cls.call_args[1]
    assert call_kwargs["db_path"] == db


def test_generate_passes_custom_config(tmp_path: Path) -> None:
    """--config option is forwarded to PortfolioReportGenerator."""
    html_path = tmp_path / "portfolio_report.html"
    html_path.touch()
    cfg = tmp_path / "my_portfolio.json"
    mock_gen = _mock_generator(html_path)
    with patch(_PATCH_GEN, return_value=mock_gen) as mock_cls:
        runner.invoke(app, ["generate", "--no-browser", "--config", str(cfg)])

    call_kwargs = mock_cls.call_args[1]
    assert call_kwargs["config_path"] == cfg
