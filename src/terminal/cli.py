import typer
from alembic.config import Config
from alembic import command
from pathlib import Path

app = typer.Typer()


def get_alembic_config(name: str = "core"):
    # Helper to load alembic.ini from the package directory
    current_dir = Path(__file__).parent
    alembic_cfg_path = current_dir / "alembic.ini"
    if not alembic_cfg_path.exists():
        raise FileNotFoundError(f"alembic.ini not found at {alembic_cfg_path}")

    # Create Alembic config object
    alembic_cfg = Config(str(alembic_cfg_path))
    if name != "alembic":
        alembic_cfg.config_ini_section = name
        if name == "core":
            script_dir = current_dir / "database/revisions/core"
            version_dir = script_dir / "versions"
            alembic_cfg.set_section_option(name, "script_location", str(script_dir))
            alembic_cfg.set_section_option(name, "version_locations", str(version_dir))
        elif name == "tenant":
            script_dir = current_dir / "database/revisions/tenant"
            version_dir = script_dir / "versions"
            alembic_cfg.set_section_option(name, "script_location", str(script_dir))
            alembic_cfg.set_section_option(name, "version_locations", str(version_dir))

    return alembic_cfg


database_app = typer.Typer()
app.add_typer(database_app, name="database")


@database_app.command()
def upgrade(
    revision: str = typer.Argument("head", help="Revision to upgrade to"),
    name: str = typer.Option("core", "-n", "--name", help="Database name"),
):
    """
    Upgrade to a later version.
    """
    alembic_cfg = get_alembic_config(name)
    command.upgrade(alembic_cfg, revision)


@database_app.command()
def downgrade(
    revision: str = typer.Argument("base", help="Revision to downgrade to"),
    name: str = typer.Option("core", "-n", "--name", help="Database name"),
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
    name: str = typer.Option("core", "-n", "--name", help="Database name"),
):
    """
    Create a new revision file.
    """
    alembic_cfg = get_alembic_config(name)
    command.revision(alembic_cfg, message=message, autogenerate=autogenerate)


@database_app.command("make-migrations")
def make_migrations(
    message: str = typer.Option(..., "-m", "--message", help="Migration message"),
    name: str = typer.Option("core", "-n", "--name", help="Database name"),
):
    """
    Autogenerate a new revision file (shortcut for revision --autogenerate).
    """
    alembic_cfg = get_alembic_config(name)
    command.revision(alembic_cfg, message=message, autogenerate=True)


if __name__ == "__main__":
    app()
