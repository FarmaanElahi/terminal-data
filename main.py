import argparse
import asyncio
import logging

from modules.alerts.worker import run_alerts_worker
from utils.fundamentals import download_fundamentals
from utils.scanner import run_full_scanner_build


async def run():
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
    return None


def main():
    # Configure the root logger
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    asyncio.run(run())


if __name__ == "__main__":
    main()
