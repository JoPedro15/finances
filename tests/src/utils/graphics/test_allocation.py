"""Unit tests for the portfolio allocation graphics generation module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from src.utils.graphics.allocation import generate_allocation_chart


def test_generate_allocation_chart_success() -> None:
    """Verifies successful chart generation with valid input lists."""
    symbols: list[str] = ["AAPL", "VWCE"]
    current_allocs: list[float] = [20.0, 80.0]
    target_allocs: list[float] = [30.0, 70.0]

    with (
        patch("src.utils.graphics.allocation.plt.savefig") as mock_savefig,
        patch("src.utils.graphics.allocation.plt.close") as mock_close,
    ):
        result_path: Path | None = generate_allocation_chart(
            symbols=symbols,
            current_allocations=current_allocs,
            target_allocations=target_allocs,
            file_name="test_chart.png",
        )

        assert result_path is not None
        assert result_path.name == "test_chart.png"
        mock_savefig.assert_called_once()
        mock_close.assert_called_once()


def test_generate_allocation_chart_mismatched_lengths() -> None:
    """Verifies that generation returns None when input dimensions mismatch."""
    symbols: list[str] = ["AAPL", "VWCE"]
    current_allocs: list[float] = [100.0]  # Mismatched length
    target_allocs: list[float] = [50.0, 50.0]

    result_path: Path | None = generate_allocation_chart(
        symbols=symbols,
        current_allocations=current_allocs,
        target_allocations=target_allocs,
    )

    assert result_path is None


def test_generate_allocation_chart_empty_inputs() -> None:
    """Verifies that generation returns None when lists are empty."""
    result_path: Path | None = generate_allocation_chart([], [], [])
    assert result_path is None


def test_generate_allocation_chart_exception_handling() -> None:
    """Verifies error handling when rendering or saving raises an exception."""
    symbols: list[str] = ["AAPL"]
    current_allocs: list[float] = [100.0]
    target_allocs: list[float] = [100.0]

    with patch(
        "src.utils.graphics.allocation.plt.savefig",
        side_effect=Exception("Rendering error"),
    ):
        result_path: Path | None = generate_allocation_chart(
            symbols=symbols,
            current_allocations=current_allocs,
            target_allocations=target_allocs,
        )

        assert result_path is None
