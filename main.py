"""Command line entry point for the QC AI web interface."""
from __future__ import annotations

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(description="AI powered browser test automation")
    parser.add_argument("--ui", action="store_true", help="launch the browser interface")
    parser.add_argument("--headless", action="store_true", help="run a test without the UI (workflow required)")
    parser.add_argument("--url", help="application URL")
    parser.add_argument("--requirements", help="plain language test requirements")
    args = parser.parse_args()

    if args.headless:
        parser.error("headless execution is not available until the graph workflow is implemented")
    if args.ui or not args.headless:
        from ui.app import launch
        launch()


if __name__ == "__main__":
    main()
