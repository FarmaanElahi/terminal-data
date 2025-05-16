import argparse
import asyncio
import logging

from dotenv import load_dotenv

# Load environment variables asap
load_dotenv()


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
        from utils.fundamentals import download_fundamentals
        return await download_fundamentals()
    if args.mode == "scan":
        from utils.scanner import run_full_scanner_build
        return await run_full_scanner_build()
    if args.mode == "alerts":
        from modules.alerts.worker import run_alerts_worker
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
