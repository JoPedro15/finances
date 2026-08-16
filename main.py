# main.py
# This script is the main entry point for the finances project.
# Its purpose is to orchestrate the different available operations.

import sys
from typing import Any, Dict, List, Optional

from utils.analysis import analyze_overall_performance
from utils.dip_detector import load_watchlist, scan_watchlist
from utils.logger.logger import logger
from utils.snapshot import display_snapshot, get_snapshot, save_snapshot


def main() -> None:
    """Main function to route to the correct operation based on command-line
    arguments."""
    available_commands: str = "get-snapshot, save-snapshot, analyze, check-dips"

    if len(sys.argv) < 2:
        logger.error("No command provided.")
        logger.info(f"Available commands: {available_commands}")
        sys.exit(1)

    command: str = sys.argv[1].lower()

    logger.info(f"Executing Command: {command}")

    if command == "get-snapshot":
        snapshot_data: Optional[Dict[str, Any]] = get_snapshot()
        if snapshot_data:
            display_snapshot(snapshot_data)
    elif command == "save-snapshot":
        snapshot_save_data: Optional[Dict[str, Any]] = get_snapshot()
        if snapshot_save_data:
            save_snapshot(snapshot_save_data)
    elif command == "analyze":
        analyze_overall_performance()
    elif command == "check-dips":
        logger.section("Scanning Watchlist for Price Dips")
        items: List[Dict[str, str]] = load_watchlist()
        matches: List[Dict[str, Any]] = scan_watchlist(items)

        if matches:
            logger.info(f"Found {len(matches)} dip opportunities:")
            for match in matches:
                logger.info(f" -> {match}")
        else:
            logger.info("No tickers met the dip criteria.")
    else:
        logger.error(f"Unknown command: '{command}'")
        logger.info(f"Available commands: {available_commands}")
        sys.exit(1)


if __name__ == "__main__":
    main()
