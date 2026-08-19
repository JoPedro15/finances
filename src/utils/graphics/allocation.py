"""Graphics generation module using matplotlib and seaborn to render
visual comparison charts for portfolio allocations.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns  # type: ignore[import-untyped]

from src.config import DATA_DIR
from src.utils.logger.logger import logger

PLOTS_DIR: Path = DATA_DIR / "plots"


def generate_allocation_chart(
    symbols: list[str],
    current_allocations: list[float],
    target_allocations: list[float],
    file_name: str = "allocation_comparison.png",
) -> Path | None:
    """Generates a visual comparison bar chart of current vs target allocations

    and saves it to the plots directory.

    Args:
        symbols: List of asset ticker symbols or names.
        current_allocations: List of current allocation percentages.
        target_allocations: List of target allocation percentages.
        file_name: Filename for the output PNG image.

    Returns:
        Path to the generated plot image file, or None if generation fails.
    """
    if (
        not symbols
        or len(symbols) != len(current_allocations)
        or len(symbols) != len(target_allocations)
    ):
        logger.error(
            "Invalid or mismatched data provided for allocation chart generation."
        )
        return None

    try:
        PLOTS_DIR.mkdir(parents=True, exist_ok=True)
        file_path: Path = PLOTS_DIR / file_name

        sns.set_theme(style="whitegrid")
        plt.figure(figsize=(10, 6))

        data: pd.DataFrame = pd.DataFrame(
            {
                "Symbol": symbols * 2,
                "Allocation (%)": current_allocations + target_allocations,
                "Type": ["Current"] * len(symbols) + ["Target"] * len(symbols),
            }
        )

        sns.barplot(
            x="Symbol",
            y="Allocation (%)",
            hue="Type",
            data=data,
            palette="muted",
        )

        plt.title(
            "Portfolio Allocation: Current vs Target",
            fontsize=14,
            fontweight="bold",
        )
        plt.xlabel("Assets", fontsize=12)
        plt.ylabel("Allocation (%)", fontsize=12)
        plt.xticks(rotation=45, ha="right")
        plt.legend(title="Allocation Type")
        plt.tight_layout()

        plt.savefig(file_path, dpi=300)
        plt.close()

        logger.success(
            f"Allocation comparison chart successfully generated at '{file_path}'."
        )
        return file_path

    except Exception as e:
        logger.error(f"Failed to generate allocation chart: {e}")
        return None
