import asyncio
import argparse

from utils.scanner import run_full_scanner_build
from utils.fundamentals import download_fundamentals


async def main():
    parser = argparse.ArgumentParser(
        description="CLI tool for downloading fundamentals or running scanner."
    )
    parser.add_argument(
        "--mode",
        choices=["download", "scan"],
        required=True,
        help="Choose 'download' to fetch fundamentals or 'scan' to run the scanner."
    )

    args = parser.parse_args()

    if args.mode == "download":
        return await download_fundamentals()
    if args.mode == "scan":
        return await run_full_scanner_build()

    print("[ERROR] Invalid mode. Use 'download' or 'scan'.")


if __name__ == "__main__":
    asyncio.run(main())
