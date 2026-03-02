import typer
from alembic.config import Config
from alembic import command
from pathlib import Path

app = typer.Typer()


def get_alembic_config(name: str = "alembic"):
    # Helper to load alembic.ini from the package directory
    current_dir = Path(__file__).parent
    alembic_cfg_path = current_dir / "alembic.ini"
    if not alembic_cfg_path.exists():
        raise FileNotFoundError(f"alembic.ini not found at {alembic_cfg_path}")

    # Create Alembic config object
    alembic_cfg = Config(str(alembic_cfg_path))
    if name != "alembic":
        alembic_cfg.config_ini_section = name

    return alembic_cfg


database_app = typer.Typer()
app.add_typer(database_app, name="database")


@database_app.command()
def upgrade(
    revision: str = typer.Argument("head", help="Revision to upgrade to"),
    name: str = typer.Option("alembic", "-n", "--name", help="Database name"),
):
    """
    Upgrade to a later version.
    """
    alembic_cfg = get_alembic_config(name)
    command.upgrade(alembic_cfg, revision)


@database_app.command()
def downgrade(
    revision: str = typer.Argument("base", help="Revision to downgrade to"),
    name: str = typer.Option("alembic", "-n", "--name", help="Database name"),
):
    """
    Revert to a previous version.
    """
    alembic_cfg = get_alembic_config(name)
    if revision == "-1":
        revision = "head-1"
    command.downgrade(alembic_cfg, revision)


@database_app.command()
def init():
    """
    Initialize the database.
    """
    from terminal.database import init_db

    init_db()
    typer.echo("Database initialized.")


@database_app.command()
def drop():
    """
    Drop the database.
    """
    from terminal.database.manage import drop_db

    if typer.confirm("Are you sure you want to drop the database?"):
        drop_db()
        typer.echo("Database dropped.")
    else:
        typer.echo("Operation cancelled.")


@database_app.command()
def revision(
    message: str = typer.Option(..., "-m", "--message", help="Migration message"),
    autogenerate: bool = typer.Option(
        False, "--autogenerate", help="Autogenerate revision"
    ),
    name: str = typer.Option("alembic", "-n", "--name", help="Database name"),
):
    """
    Create a new revision file.
    """
    alembic_cfg = get_alembic_config(name)
    command.revision(alembic_cfg, message=message, autogenerate=autogenerate)


@database_app.command("make-migrations")
def make_migrations(
    message: str = typer.Option(..., "-m", "--message", help="Migration message"),
    name: str = typer.Option("alembic", "-n", "--name", help="Database name"),
):
    """
    Autogenerate a new revision file (shortcut for revision --autogenerate).
    """
    alembic_cfg = get_alembic_config(name)
    command.revision(alembic_cfg, message=message, autogenerate=True)


# ... (existing database_app commands)

symbol_app = typer.Typer()
app.add_typer(symbol_app, name="symbol")


@symbol_app.command("refresh")
def refresh_symbols(
    market: str = typer.Option("india", help="Market to sync symbols for"),
):
    """
    Fetch symbols from TradingView and upsert them into OCIFS.
    """
    import asyncio
    from terminal.config import settings
    from terminal.dependencies import get_fs
    from terminal.symbols import service as symbol_service

    async def _run():
        typer.echo(f"Fetching symbols for market '{market}' from TradingView...")
        fs = get_fs()
        symbols = await symbol_service.get_all_symbols_external()

        if not symbols:
            typer.echo("No symbols returned from TradingView.")
            return

        typer.echo(f"Syncing {len(symbols)} symbols to OCIFS...")
        count = await symbol_service.refresh(fs, settings, symbols)
        typer.echo(f"Successfully upserted {count} symbols.")

    asyncio.run(_run())


data_app = typer.Typer()
app.add_typer(data_app, name="market-data")


@data_app.command("refresh-daily")
def refresh_candle_day():
    """
    Refresh 1D candle data from TradingView and save to OCI cache.
    """
    import asyncio
    from terminal.config import settings
    from terminal.dependencies import (
        _get_tradingview_provider_instance,
        get_fs,
    )
    from terminal.symbols import service as symbol_service

    async def _run():
        typer.echo("Initializing providers...")
        tv_provider = _get_tradingview_provider_instance()

        typer.echo("Fetching symbol list from OCIFS...")
        fs = get_fs()
        await symbol_service.init(fs, settings)
        symbols_info = await symbol_service.search(
            fs=fs, settings=settings, limit=20000
        )  # Get all primary symbols
        tickers = [s["ticker"] for s in symbols_info]

        if not tickers:
            typer.echo("No symbols found to refresh.")
            return

        typer.echo(f"Refreshing candles for {len(tickers)} symbols...")
        await tv_provider.refresh_cache(tickers)
        typer.echo("Refresh complete.")

    asyncio.run(_run())


@data_app.command("download-bars")
def download_bars(
    timeframe: str = typer.Option(
        "1D", "--timeframe", "-t", help="TradingView timeframe (e.g. 1D, 1W, 240)"
    ),
    limit: int = typer.Option(
        20000, "--limit", "-l", help="Max number of symbols to download"
    ),
):
    """
    Download full historical bar series from TradingView via WebSocket streamer
    and save to OCI cache. Uses streamer2.py for efficient bulk streaming.
    """
    import asyncio
    from terminal.config import settings
    from terminal.dependencies import (
        _get_tradingview_provider_instance,
        get_fs,
    )
    from terminal.symbols import service as symbol_service

    async def _run():
        typer.echo("Initializing providers...")
        tv_provider = _get_tradingview_provider_instance()

        typer.echo("Fetching symbol list from OCIFS...")
        fs = get_fs()
        await symbol_service.init(fs, settings)
        symbols_info = await symbol_service.search(
            fs=fs, settings=settings, limit=limit
        )
        tickers = [s["ticker"] for s in symbols_info]

        if not tickers:
            typer.echo("No symbols found.")
            return

        total = len(tickers)
        typer.echo(f"Downloading bars for {total} symbols (timeframe={timeframe})...")

        def on_progress(completed: int, total: int):
            if completed % 100 == 0 or completed == total:
                typer.echo(f"  Progress: {completed}/{total} symbols")

        saved = await tv_provider.download_bars(
            tickers, timeframe=timeframe, on_progress=on_progress
        )
        typer.echo(f"Done. Saved bar data for {saved} symbols to OCIFS.")

    asyncio.run(_run())


health_app = typer.Typer()
app.add_typer(health_app, name="health")


@health_app.callback(invoke_without_command=True)
def health_check():
    """Run a CLI health check against DB, OCI, and external APIs."""
    import asyncio
    from terminal.config import settings
    from terminal.dependencies import get_fs

    async def _run():
        checks = {}

        # 1. Database
        try:
            from terminal.database.core import engine
            from sqlalchemy import text

            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            checks["database"] = "ok"
            typer.echo("  Database: OK")
        except Exception as e:
            checks["database"] = f"error: {e}"
            typer.echo(f"  Database: FAIL ({e})")

        # 2. OCI
        try:
            fs = get_fs()
            fs.ls(settings.oci_bucket)
            checks["oci"] = "ok"
            typer.echo("  OCI Storage: OK")
        except Exception as e:
            checks["oci"] = f"error: {e}"
            typer.echo(f"  OCI Storage: FAIL ({e})")

        # 3. TradingView Scanner
        try:
            from terminal.tradingview.scanner import TradingViewScanner

            scanner = TradingViewScanner()
            result = await scanner.fetch_ohlcv()
            checks["tradingview"] = f"ok ({len(result)} symbols)"
            typer.echo(f"  TradingView Scanner: OK ({len(result)} symbols)")
        except Exception as e:
            checks["tradingview"] = f"error: {e}"
            typer.echo(f"  TradingView Scanner: FAIL ({e})")

        all_ok = all(v.startswith("ok") for v in checks.values())
        typer.echo(f"\nOverall: {'HEALTHY' if all_ok else 'UNHEALTHY'}")
        raise SystemExit(0 if all_ok else 1)

    asyncio.run(_run())


@database_app.command("backup")
def backup_database(
    output: str = typer.Option(
        "backup.sql",
        "--output",
        "-o",
        help="Output file path for the backup",
    ),
):
    """Create a pg_dump backup of the database."""
    import subprocess
    import os
    from terminal.config import settings
    from urllib.parse import urlparse

    parsed = urlparse(settings.database_url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 5432
    user = parsed.username or "postgres"
    dbname = parsed.path.lstrip("/")

    env = {**os.environ, "PGPASSWORD": parsed.password or ""}

    typer.echo(f"Backing up {dbname}@{host}:{port} to {output}...")
    try:
        subprocess.run(
            [
                "pg_dump",
                "-h",
                host,
                "-p",
                str(port),
                "-U",
                user,
                "-d",
                dbname,
                "-f",
                output,
            ],
            env=env,
            check=True,
        )
        typer.echo(f"Backup saved to {output}")
    except subprocess.CalledProcessError as e:
        typer.echo(f"Backup failed: {e}", err=True)
        raise typer.Exit(1)
    except FileNotFoundError:
        typer.echo("pg_dump not found. Install PostgreSQL client tools.", err=True)
        raise typer.Exit(1)


@database_app.command("restore")
def restore_database(
    input_file: str = typer.Argument(..., help="Path to the backup file"),
):
    """Restore a database from a pg_dump backup."""
    import subprocess
    import os
    from terminal.config import settings
    from urllib.parse import urlparse

    parsed = urlparse(settings.database_url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 5432
    user = parsed.username or "postgres"
    dbname = parsed.path.lstrip("/")

    env = {**os.environ, "PGPASSWORD": parsed.password or ""}

    if not typer.confirm(f"This will restore {input_file} into {dbname}. Continue?"):
        typer.echo("Cancelled.")
        return

    typer.echo(f"Restoring {input_file} into {dbname}@{host}:{port}...")
    try:
        subprocess.run(
            [
                "psql",
                "-h",
                host,
                "-p",
                str(port),
                "-U",
                user,
                "-d",
                dbname,
                "-f",
                input_file,
            ],
            env=env,
            check=True,
        )
        typer.echo("Restore complete.")
    except subprocess.CalledProcessError as e:
        typer.echo(f"Restore failed: {e}", err=True)
        raise typer.Exit(1)


@data_app.command("validate")
def validate_market_data():
    """Validate OCI market data cache integrity (row counts, date ranges, null checks)."""
    import asyncio
    from terminal.dependencies import _get_tradingview_provider_instance, get_fs

    async def _run():
        typer.echo("Validating market data cache...")
        fs = get_fs()
        provider = _get_tradingview_provider_instance()

        # Check if cache file exists in OCI
        if not fs.exists(provider.cache_file_oci):
            typer.echo(f"  OCI cache not found: {provider.cache_file_oci}")
            raise typer.Exit(1)

        # Load and validate
        try:
            provider.load_cache()
        except Exception as e:
            typer.echo(f"  Failed to load cache: {e}")
            raise typer.Exit(1)

        tickers = provider.get_all_tickers()
        typer.echo(f"  Symbols in cache: {len(tickers)}")

        if not tickers:
            typer.echo("  WARNING: No symbols in cache!")
            raise typer.Exit(1)

        # Sample validation
        null_count = 0
        empty_count = 0
        for ticker in tickers[:100]:
            df = provider.get_history(ticker)
            if df is None or len(df) == 0:
                empty_count += 1
                continue
            nulls = df.isnull().sum().sum()
            if nulls > 0:
                null_count += 1

        typer.echo(
            f"  Sample check (first 100): {empty_count} empty, {null_count} with nulls"
        )

        if empty_count > 50:
            typer.echo("  WARNING: >50% of sampled symbols have no data!")
        else:
            typer.echo("  Validation passed.")

    asyncio.run(_run())


if __name__ == "__main__":
    app()
