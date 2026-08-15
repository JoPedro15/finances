# main.py
# This script is the main entry point for the finances project.
# Its purpose is to orchestrate the different available operations.

import sys
from utils.snapshot import get_snapshot, display_snapshot, save_snapshot
from utils.analysis import analyze_overall_performance
from utils.logger.logger import logger


def main():
    """
    Main function to route to the correct operation based on command-line arguments.
    """
    if len(sys.argv) < 2:
        logger.error("No command provided.")
        logger.info("Available commands: get-snapshot, save-snapshot, analyze")
        sys.exit(1)

    command = sys.argv[1].lower()

    logger.info(f"Executing Command: {command}")

    if command == "get-snapshot":
        snapshot_data = get_snapshot()
        if snapshot_data:
            display_snapshot(snapshot_data)
    elif command == "save-snapshot":
        snapshot_data = get_snapshot()
        if snapshot_data:
            save_snapshot(snapshot_data)
    elif command == "analyze":
        analyze_overall_performance()
    else:
        logger.error(f"Unknown command: '{command}'")
        logger.info("Available commands: get-snapshot, save-snapshot, analyze")
        sys.exit(1)


if __name__ == "__main__":
    main()
