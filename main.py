import asyncio
import argparse

from utils.scanner import run_full_scanner_build
from utils.fundamentals import download_fundamentals
from modules.alerts.worker import run_alerts_worker


async def main():
    parser = argparse.ArgumentParser(
        description="CLI tool for downloading fundamentals or running scanner."
    )
    parser.add_argument(
        "--mode",
        choices=["download", "scan", "alerts"],
        required=True,
        help="Choose 'download' to fetch fundamentals or 'scan' to run the scanner."
    )

    args = parser.parse_args()

    if args.mode == "download":
        return await download_fundamentals()
    if args.mode == "scan":
        return await run_full_scanner_build()
    if args.mode == "alerts":
        return await run_alerts_worker()

    print("[ERROR] Invalid mode. Use 'download' or 'scan'.")


if __name__ == "__main__":
    asyncio.run(main())
